import sumBy from 'lodash/sumBy';

import { set_charge_type_query } from './utils';
import Timeline from '../vue/Timeline.vue';

function set_address(party_type) {
  const address_field = `${party_type}_address`;
  return async function (frm) {
    if (frm.doc[party_type]) {
      const { message: { primary_address } = {} } = await frappe.db.get_value(
        'Booking Party',
        frm.doc[party_type],
        'primary_address'
      );
      frm.set_value(address_field, primary_address);
    } else {
      frm.set_value(address_field, null);
    }
  };
}

function set_address_dispay(party_type) {
  const address_field = `${party_type}_address`;
  const display_field = `${party_type}_address_display`;
  return async function (frm) {
    erpnext.utils.get_address_display(frm, address_field, display_field);
  };
}

function set_total_amount(frm) {
  const total_amount = sumBy(frm.doc.charges, 'charge_amount');
  frm.set_value({ total_amount });
}
async function update_party_details(frm) {
  const { message } = await frappe.call({
    method: 'gg_custom.api.booking_order.update_party_details',
    args: { name: frm.doc.name },
  });
  frm.reload_doc();
}

export function booking_order_charge() {
  return {
    charge_amount: set_total_amount,
    charges_remove: set_total_amount,
  };
}

export function booking_order() {
  return {
    setup: function (frm) {
      ['consignor', 'consignee'].forEach((type) => {
        frm.set_query(type, (doc) => ({
          filters: { disabled: 0 },
        }));
        frm.set_query(`${type}_address`, (doc) => ({
          filters: { link_doctype: 'Booking Party', link_name: doc[type] },
        }));
      });
      set_charge_type_query(frm);
    },
    refresh: function (frm) {
      if (frm.doc.docstatus === 1) {
        const { status, current_station, destination_station } = frm.doc;
        if (frm.doc.__onload && frm.doc.__onload.no_of_deliverable_packages) {
          frm.add_custom_button('Deliver', handle_deliver(frm));
        }

        frm
          .add_custom_button('Create Invoice', () => create_invoice(frm))
          .addClass('btn-primary');

        const {
          dashboard_info: { invoice: { outstanding_amount = 0 } = {} } = {},
        } = frm.doc.__onload || {};
        if (outstanding_amount > 0) {
          frm.add_custom_button('Create Payment', () => create_payment(frm));
        }
        frm.page.add_menu_item('Update Party Details', () =>
          update_party_details(frm)
        );
      }
      if (frm.doc.docstatus > 0) {
        const { dashboard_info } = frm.doc.__onload || {};
        if (dashboard_info) {
          render_dashboard(frm, dashboard_info);
        }
      }
    },
    consignor: set_address('consignor'),
    consignee: set_address('consignee'),
    consignor_address: set_address_dispay('consignor'),
    consignee_address: set_address_dispay('consignee'),
    booking_order_charge_template: async function (frm) {
      cur_frm.clear_table('charges');
      const { booking_order_charge_template } = frm.doc;
      if (booking_order_charge_template) {
        const charges = await frappe.db.get_list('Booking Order Charge', {
          fields: ['charge_type', 'charge_amount'],
          parent: 'Booking Order Charge Template',
          filters: {
            parenttype: 'Booking Order Charge Template',
            parent: booking_order_charge_template,
          },
          order_by: 'idx',
        });
        charges.forEach((row) => {
          frm.add_child('charges', row);
        });
      }
      cur_frm.refresh_field('charges');
      set_total_amount(frm);
    },
  };
}

export function booking_order_listview_settings() {
  const status_color = {
    Draft: 'red',
    Booked: 'darkgrey',
    'In Progress': 'blue',
    Collected: 'green',
    Cancelled: 'red',
    Unknown: 'darkgrey',
  };
  return {
    filters: [['docstatus', '!=', 2]],
    get_indicator: function (doc) {
      const status = doc.status || 'Unknown';
      return [__(status), status_color[status] || 'grey', `status,=,${status}`];
    },
  };
}

function render_dashboard(frm, dashboard_info) {
  const props = { ...dashboard_info };
  if (dashboard_info && dashboard_info.invoice) {
    const { grand_total, outstanding_amount } = dashboard_info.invoice;
    cur_frm.dashboard.add_indicator(
      `Total Billed: ${format_currency(grand_total)}`,
      'green'
    );
    cur_frm.dashboard.add_indicator(
      `Outstanding Amount: ${format_currency(outstanding_amount)}`,
      'orange'
    );
  }
  new Vue({
    el: frm.dashboard.add_section('<div />').children()[0],
    render: (h) => h(Timeline, { props }),
  });
}

function create_invoice(frm) {
  const dialog = new frappe.ui.Dialog({
    title: 'Create Invoice',
    fields: [
      {
        fieldtype: 'Select',
        fieldname: 'bill_to',
        label: __('Bill To'),
        options: [
          {
            label: `Consignor: ${frm.doc.consignor}`,
            value: 'consignor',
          },
          {
            label: `Consignee: ${frm.doc.consignee}`,
            value: 'consignee',
          },
        ],
        default: 'consignor',
      },
      {
        fieldtype: 'Link',
        fieldname: 'taxes_and_charges',
        label: __('Sales Taxes and Charges Template'),
        options: 'Sales Taxes and Charges Template',
        only_select: 1,
      },
    ],
  });
  dialog.set_primary_action('OK', async function () {
    const args = dialog.get_values();
    frappe.model.open_mapped_doc({
      method: 'gg_custom.api.booking_order.make_sales_invoice',
      frm,
      args,
    });
    dialog.hide();
  });
  dialog.onhide = () => dialog.$wrapper.remove();
  dialog.show();
}

function create_payment(frm) {
  frappe.model.open_mapped_doc({
    method: 'gg_custom.api.booking_order.make_payment_entry',
    frm,
  });
}

function handle_deliver(frm) {
  return async function () {
    const dialog = new frappe.ui.Dialog({
      title: 'Deliver',
      fields: [
        {
          fieldtype: 'Int',
          fieldname: 'no_of_packages',
          reqd: 1,
          label: 'No of Packages',
          default: frm.doc.__onload.no_of_deliverable_packages,
        },
      ],
    });
    dialog.set_primary_action('OK', async function () {
      try {
        const no_of_packages = dialog.get_value('no_of_packages');
        await frm.call('deliver', { no_of_packages });
        frm.reload_doc();
        dialog.hide();
      } finally {
        frm.refresh();
      }
    });
    dialog.onhide = () => dialog.$wrapper.remove();
    dialog.show();
  };
}
