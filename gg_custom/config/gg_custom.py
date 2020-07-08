from __future__ import unicode_literals
import frappe


def get_data():
    return [
        {
            "label": frappe._("Booking"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Booking Order",
                    "description": frappe._("Booking Order"),
                },
                {
                    "type": "doctype",
                    "name": "Booking Party",
                    "description": frappe._("Consignor / Consignee Details"),
                },
            ],
        },
        {
            "label": frappe._("Setup"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Booking Order Charge Template",
                    "description": frappe._("Booking Order Charge Template"),
                },
                {
                    "type": "doctype",
                    "name": "Station",
                    "description": frappe._("Station"),
                },
            ],
        },
    ]
