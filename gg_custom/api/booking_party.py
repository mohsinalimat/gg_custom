from __future__ import unicode_literals
import frappe

from gg_custom.api.booking_order import get_payment_entry_from_invoices


def get_party_open_orders(party):
    sales_invoices = [
        frappe.get_cached_doc("Sales Invoice", x.get("name"))
        for x in frappe.db.sql(
            """
                SELECT name FROM `tabSales Invoice`
                WHERE docstatus = 1 AND outstanding_amount > 0 AND customer = %(customer)s
            """,
            values={
                "customer": frappe.get_cached_value("Booking Party", party, "customer")
            },
            as_dict=1,
        )
    ]

    booking_orders = [
        frappe.get_cached_doc("Booking Order", name)
        for name in set([x.gg_booking_order for x in sales_invoices if x])
    ]

    return {"booking_orders": booking_orders, "sales_invoices": sales_invoices}


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    customer = frappe.get_cached_value("Booking Party", source_name, "customer")
    invoices = [
        frappe.get_cached_doc("Sales Invoice", x.get("name"))
        for x in frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "customer": customer,
                "outstanding_amount": [">", 0],
            },
            order_by="posting_date, name",
        )
    ]

    return get_payment_entry_from_invoices(invoices)


def update_customer(name):
    doc = frappe.get_doc("Booking Party", name)
    if doc and doc.customer:
        customer = frappe.get_cached_doc("Customer", doc.customer)
        for booking_party_field, customer_field in [
            ("booking_party_name", "customer_name"),
            ("primary_address", "customer_primary_address"),
        ]:
            if customer and (
                customer.get(booking_party_field) != doc.get(booking_party_field)
            ):
                frappe.db.set_value(
                    "Customer",
                    doc.customer,
                    customer_field,
                    doc.get(booking_party_field),
                )
