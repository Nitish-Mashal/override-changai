(function () {
	"use strict";

	var HOST_ID = "changai-chatbot-host";
	var OLD_HEADER = "ChangAI from ERPGulf";
	var NEW_HEADER = "Q-DynamicsAI";
	var NEW_GREETING = "Hello there \ud83d\udc4b I am Q-DynamicsAI, your ERP assistant.";

	function isOldHeader(el) {
		return el.tagName === "H2" && el.textContent.trim() === OLD_HEADER;
	}

	function isOldGreeting(el) {
		if (el.tagName !== "P") return false;
		var text = el.textContent;
		return (
			text.indexOf("Hello there") !== -1 &&
			text.indexOf("your ERP assistant") !== -1 &&
			text.indexOf("ERPGulf.com") !== -1 &&
			text.trim() !== NEW_GREETING
		);
	}

	function patch(root) {
		var els = root.querySelectorAll("h2, p");
		for (var i = 0; i < els.length; i++) {
			var el = els[i];
			if (isOldHeader(el)) {
				el.textContent = NEW_HEADER;
			} else if (isOldGreeting(el)) {
				el.textContent = NEW_GREETING;
			}
		}
	}

	function watchShadow(host) {
		var root = host.shadowRoot;
		if (!root || root.__qdWatched) return;
		root.__qdWatched = true;
		patch(root);
		var observer = new MutationObserver(function () {
			patch(root);
		});
		observer.observe(root, {
			childList: true,
			subtree: true,
			characterData: true,
		});
	}

	function findHost() {
		var host = document.getElementById(HOST_ID);
		if (host) watchShadow(host);
	}

	function start() {
		findHost();
		var observer = new MutationObserver(findHost);
		observer.observe(document.documentElement, {
			childList: true,
			subtree: true,
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start);
	} else {
		start();
	}
})();
