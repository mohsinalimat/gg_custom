# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from erpnext.accounts.report.general_ledger.general_ledger import get_gl_entries
from erpnext.accounts.party import get_party_account
from toolz.curried import groupby, valmap, first, compose, merge


def execute(filters=None):
    return _get_columns(filters), _get_data(filters)


def _get_columns(filters):
    return [
        {
            "fieldtype": "Date",
            "fieldname": "posting_date",
            "label": "Posting Date",
            "print_width": 300,
            "width": 90,
        },
        {
            "fieldtype": "Data",
            "fieldname": "voucher_type",
            "label": "Voucher Type",
            "width": 120,
        },
        {
            "fieldtype": "Dynamic Link",
            "fieldname": "voucher_no",
            "options": "voucher_type",
            "label": "Voucher No",
            "width": 180,
        },
        {
            "fieldtype": "Currency",
            "fieldname": "amount",
            "label": "Amount",
            "width": 90,
        },
        {
            "fieldtype": "Link",
            "fieldname": "booking_order",
            "options": "Booking Order",
            "label": "Booking Order",
            "width": 120,
        },
        {
            "fieldtype": "Data",
            "fieldname": "description",
            "label": "Description",
            "width": 300,
        },
        {
            "fieldtype": "Data",
            "fieldname": "vehicles",
            "label": "Vehicles",
            "width": 180,
        },
    ]


def _get_data(filters):
    company = frappe.defaults.get_user_default("company")
    customer = frappe.get_cached_value(
        "Booking Party", filters.booking_party, "customer"
    )
    account = get_party_account("Customer", customer, company,)
    gl_entries = get_gl_entries(
        {
            "from_date": filters.get("from_date"),
            "to_date": filters.get("to_date"),
            "company": company,
            "account": account,
            "party_type": "Customer",
            "party": [customer],
        }
    )

    invoices = [
        x.get("voucher_no")
        for x in gl_entries
        if x.get("voucher_type") == "Sales Invoice"
    ]
    get_booking_orders = compose(valmap(first), groupby("sales_invoice"), frappe.db.sql)
    booking_orders = (
        get_booking_orders(
            """
                SELECT
                    si.name AS sales_invoice,
                    bo.name,
                    bo.no_of_packages,
                    bo.weight_charged,
                    bo.packing
                FROM `tabSales Invoice` AS si
                LEFT JOIN `tabBooking Order` AS bo ON bo.name = si.gg_booking_order
                WHERE si.name IN %(invoices)s
            """,
            values={"invoices": invoices},
            as_dict=1,
        )
        if invoices
        else {}
    )

    orders = [v.get("name") for _, v in booking_orders.items()]
    get_descriptions = compose(groupby("parent"), frappe.db.sql)
    descriptions = (
        get_descriptions(
            """
                SELECT bofd.parent, bofd.based_on, bofd.item_description, bofd.qty, bofd.rate
                FROM `tabBooking Order Freight Detail` As bofd
                LEFT JOIN `tabBooking Order` AS bo ON bo.name = bofd.parent
                WHERE bo.name IN %(orders)s
            """,
            values={"orders": orders},
            as_dict=1,
        )
        if orders
        else {}
    )

    get_vehicles = compose(groupby("booking_order"), frappe.db.sql)
    vehicles = (
        get_vehicles(
            """
                SELECT so.vehicle, bl.booking_order FROM `tabBooking Log` As bl
                LEFT JOIN `tabShipping Order` AS so ON so.name = bl.shipping_order
                WHERE bl.activity = 'Loaded' AND bl.booking_order IN %(orders)s
            """,
            values={"orders": orders},
            as_dict=1,
        )
        if orders
        else {}
    )

    def make_message(freight):
        return freight.get("item_description")
        # rate = frappe.utils.fmt_money(
        #     freight.get("rate"), currency=frappe.defaults.get_global_default("currency")
        # )
        # if freight.get("based_on") == "Weight":
        #     return "{} by weight @ {} - {}".format(
        #         freight.get("qty"), rate, freight.get("item_description")
        #     )

        # return "{} packages @ {} - {}".format(
        #     freight.get("qty"), rate, freight.get("item_description")
        # )

    def make_description(bo):
        return ", ".join([make_message(x) for x in descriptions.get(bo, [])])

    def make_vehicles(bo):
        return ", ".join(set([x.get("vehicle") for x in vehicles.get(bo, [])]))

    def make_row(row):
        booking_order = booking_orders.get(row.get("voucher_no"), {})
        bo_name = booking_order.get("name")
        return merge(
            row,
            {
                "amount": row.get("debit") - row.get("credit"),
                "booking_order": bo_name,
                "description": make_description(bo_name)
                if row.get("voucher_type") == "Sales Invoice"
                else row.get("remarks"),
                "vehicles": make_vehicles(bo_name),
            },
        )

    return [make_row(x) for x in gl_entries]
