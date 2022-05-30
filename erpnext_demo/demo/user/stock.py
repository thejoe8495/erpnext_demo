# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import random

import frappe
from frappe.desk import query_report

import erpnext
from erpnext.stock.doctype.batch.batch import UnableToSelectBatchError
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_return
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_return
from erpnext.stock.doctype.serial_no.serial_no import SerialNoQtyError, SerialNoRequiredError
from erpnext.stock.stock_ledger import NegativeStockError


def work():
	frappe.set_user(frappe.db.get_global("demo_manufacturing_user"))

	make_purchase()
	make_delivery_note()
	make_stock_reconciliation()
	submit_draft_stock_entries()
	make_sales_return_records()
	make_purchase_return_records()

def make_purchase():
	if random.random() < 0.6:
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
		
		for po in frappe.get_all("Purchase Order", ["name"], {"status": "To Receive and Bill"})[:random.randint(1, 7)]:
			po_doc = frappe.get_doc("Purchase Order", po.name)
			pr = frappe.get_doc(make_purchase_receipt(po_doc.name))

			if pr.is_subcontracted=="Yes":
				pr.supplier_warehouse = "Supplier - WPL"
			pr.rounded_total = po_doc.rounded_total
			pr.grand_total = po_doc.grand_total
			pr.base_net_total = po_doc.base_net_total
			pr.posting_date = frappe.flags.current_date
			pr.set_posting_time = True
			for po_items in po_doc.items:
				pr.append("items", {
					"item_code": po_items.item_code,
					#"schedule_date": frappe.utils.add_days(frappe.flags.current_date, 7),
					"qty": po_items.qty,
					"rate" : po_items.rate
					#"rate": 16
				})
			pr.set_missing_values(po)
			pr.insert()
			try:
				pr.submit()
			except NegativeStockError:
				print("Negative stock for {0}".format(po))
				pass
			frappe.db.commit()


def make_delivery_note():
	# make purchase requests

	# make delivery notes (if possible)
	if random.random() < 0.6:
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		report = "Pending SO Items For Purchase Request"
		for so in query_report.run(report, {"from_date": frappe.utils.add_days(frappe.flags.current_date, -100), "to_date": frappe.flags.current_date })["result"][:random.randint(1, 13)]:
			so_doc = frappe.get_doc("Sales Order", so["sales_order_no"])
			dn = frappe.get_doc(make_delivery_note(so["sales_order_no"]))
			dn.posting_date = frappe.flags.current_date
			dn.set_posting_time = True
			for so_items in so_doc.items:
				dn.append("items", {
					"item_code": so_items.item_code,
					#"schedule_date": frappe.utils.add_days(frappe.flags.current_date, 7),
					"qty": so_items.qty,
					"rate" : so_items.rate,
					"expense_account": ("Cost of Goods Sold - {0}".format(
						frappe.get_cached_value('Company',  dn.company,  'abbr')))
					#"rate": 16
				})
			try:
				dn.insert()
				dn.submit()
				frappe.db.commit()
			except (NegativeStockError, SerialNoRequiredError, SerialNoQtyError, UnableToSelectBatchError):
				frappe.db.rollback()


def make_stock_reconciliation():
	# random set some items as damaged
	from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
		EmptyStockReconciliationItemsError,
		OpeningEntryAccountError,
	)

	if random.random() < 0.4:
		stock_reco = frappe.new_doc("Stock Reconciliation")
		stock_reco.posting_date = frappe.flags.current_date
		stock_reco.company = erpnext.get_default_company()
		stock_reco.get_items_for("Stores - WPL")
		if stock_reco.items:
			for item in stock_reco.items:
				if item.qty:
					item.qty = item.qty - round(random.randint(1, item.qty))
					item.valuation_rate = 16
			try:
				stock_reco.insert(ignore_permissions=True, ignore_mandatory=True)
				stock_reco.submit()
				frappe.db.commit()
			except OpeningEntryAccountError:
				frappe.db.rollback()
			except EmptyStockReconciliationItemsError:
				frappe.db.rollback()


def submit_draft_stock_entries():
	from erpnext.stock.doctype.stock_entry.stock_entry import (
		DuplicateEntryForWorkOrderError,
		IncorrectValuationRateError,
		OperationsNotCompleteError,
	)

	# try posting older drafts (if exists)
	frappe.db.commit()
	for st in frappe.db.get_values("Stock Entry", {"docstatus": 0}, "name"):
		try:
			ste = frappe.get_doc("Stock Entry", st[0])
			ste.posting_date = frappe.flags.current_date
			ste.save()
			ste.submit()
			frappe.db.commit()
		except (
			NegativeStockError,
			IncorrectValuationRateError,
			DuplicateEntryForWorkOrderError,
			OperationsNotCompleteError,
		):
			frappe.db.rollback()


def make_sales_return_records():
	if random.random() < 0.1:
		for data in frappe.get_all("Delivery Note", fields=["name"], filters={"docstatus": 1}):
			if random.random() < 0.1:
				try:
					dn = make_sales_return(data.name)
					dn.insert()
					dn.submit()
					frappe.db.commit()
				except Exception:
					frappe.db.rollback()


def make_purchase_return_records():
	if random.random() < 0.1:
		for data in frappe.get_all("Purchase Receipt", fields=["name"], filters={"docstatus": 1}):
			if random.random() < 0.1:
				try:
					pr = make_purchase_return(data.name)
					pr.insert()
					pr.submit()
					frappe.db.commit()
				except Exception:
					frappe.db.rollback()
