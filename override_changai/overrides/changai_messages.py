"""Suppress the ChangAI FAISS master-store notice without touching its cause.

``changai.changai.api.v2.retrieve.get_master_vs`` raises with
``frappe.throw`` when the per-site master vector store
(``private/changai/fvs_stores/erpnext/masterdata_fvs``) is missing.  In
Frappe, :func:`frappe.throw` runs ``msgprint``, which appends the text to
``frappe.local.message_log`` *before* the exception is raised
(``frappe/utils/messages.py``).  ``get_master_vs`` swallows its own
exception and only writes an Error Log, so the message survives in the log
and ``_make_logs_v1`` serialises it into the response's
``_server_messages``.  The login page renders that as the FAISS popup
after ``on_session_creation`` runs ``retrieve.load_on_startup``.

The hooks below drop **only** entries whose text carries the exact
ChangAI master-store marker.  Every other message, warning and exception
keeps flowing unchanged, and the original throw, catch and Error Log
entry in ``changai`` are left exactly as they are - this suppresses the
display, not the failure.

Registered in ``override_changai/hooks.py`` as:

* ``on_session_creation`` - runs after changai's ``load_on_startup`` and
  ``reload_mapping_schema_cache`` (override_changai is installed after
  changai, so ``_load_app_hooks`` appends our entry last) and before
  ``frappe.utils.response`` builds ``_server_messages``.  This is the
  point that keeps the popup off ``/login``.
* ``after_request`` - safety net for any later JSON response (desk or
  chat API) that inherits the same swallowed throw; skips payload
  re-serialisation unless the marker bytes are present at all.
"""

import json

import frappe

# Exact opening of the changai master-store message
# (retrieve.py: "FAISS MASTER store not found at {0}...").
FAISS_MASTER_MARKER = "FAISS MASTER store not found at"


def _is_faiss_master_notice(entry) -> bool:
	"""True only for the ChangAI FAISS master-store message entry."""

	if isinstance(entry, dict):
		entry = entry.get("message")
	elif not isinstance(entry, str):
		return False

	if isinstance(entry, str):
		return FAISS_MASTER_MARKER in entry
	if isinstance(entry, (list, tuple)):
		return any(
			isinstance(cell, str) and FAISS_MASTER_MARKER in cell for cell in entry
		)
	return False


def drop_changai_master_store_message(login_manager=None) -> None:
	"""``on_session_creation`` hook: forget the master-store notice.

	Runs in the same login request, after changai's warmup hooks have
	appended the message and before the response serialises
	``frappe.local.message_log``.  Removes matching entries only.
	"""

	message_log = getattr(frappe.local, "message_log", None)
	if not message_log:
		return

	kept = [
		entry for entry in message_log if not _is_faiss_master_notice(entry)
	]
	if len(kept) != len(message_log):
		# In-place slice keeps the very same list object bound to
		# frappe.message_log (a LocalProxy) for the rest of the request.
		message_log[:] = kept


def strip_faiss_master_from_response(response=None, request=None) -> None:
	"""``after_request`` hook: drop the notice from an already-built JSON body.

	``_make_logs_v1`` has already folded ``message_log`` into
	``_server_messages`` (v1) or ``messages`` (v2) by the time this runs,
	so scrub the payload directly - but only when the raw bytes actually
	contain the marker, which keeps the cost a substring search for the
	common case.
	"""

	if response is None or not getattr(response, "is_json", False):
		return

	try:
		data = response.get_data(as_text=True)
	except (TypeError, ValueError, AttributeError):
		return

	if not data or FAISS_MASTER_MARKER not in data:
		return

	try:
		payload = json.loads(data)
	except (TypeError, ValueError):
		return

	if not isinstance(payload, dict):
		return

	changed = False

	# v1: _server_messages is a list of JSON-encoded message dicts.
	server_messages = payload.get("_server_messages")
	if isinstance(server_messages, str):
		try:
			entries = json.loads(server_messages)
		except (TypeError, ValueError):
			entries = None
		if isinstance(entries, list):
			kept = [
				entry
				for entry in entries
				if not (
					isinstance(entry, str)
					and FAISS_MASTER_MARKER in entry
				)
			]
			if len(kept) != len(entries):
				payload["_server_messages"] = json.dumps(kept, ensure_ascii=False)
				changed = True
			if not kept:
				payload.pop("_server_messages")
				changed = True

	# v2: messages is a list of message dicts.
	messages = payload.get("messages")
	if isinstance(messages, list):
		kept = [
			entry for entry in messages if not _is_faiss_master_notice(entry)
		]
		if len(kept) != len(messages):
			if kept:
				payload["messages"] = kept
			else:
				payload.pop("messages")
			changed = True

	if changed:
		response.set_data(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
