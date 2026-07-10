(function () {
  "use strict";

  /* ---------- Intro animation ---------- */
  var introOverlay = document.getElementById("intro-overlay");
  if (introOverlay) {
    var removeIntro = function () {
      introOverlay.style.display = "none";
      document.body.style.overflow = "";
    };
    var skipIntro = function () {
      introOverlay.classList.add("is-skipped");
    };
    var alreadyPlayed = getComputedStyle(introOverlay).animationName === "none";
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (alreadyPlayed || reducedMotion) {
      removeIntro();
    } else {
      document.body.style.overflow = "hidden";
      introOverlay.addEventListener("click", skipIntro);
      introOverlay.addEventListener("animationend", function (e) {
        if (e.target === introOverlay) removeIntro();
      });
    }
  }

  /* ---------- Mobile nav ---------- */
  var navToggle = document.getElementById("nav-toggle");
  var mainNav = document.getElementById("main-nav");
  navToggle.addEventListener("click", function () {
    var isOpen = mainNav.classList.toggle("is-open");
    navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });
  mainNav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      mainNav.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });

  /* ---------- Toast ---------- */
  var toastEl = document.getElementById("toast");
  var toastTimer = null;
  function showToast(message) {
    toastEl.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg><span>' +
      message +
      "</span>";
    toastEl.classList.add("is-visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("is-visible");
    }, 3200);
  }

  /* ---------- Cart ---------- */
  var cart = []; // { name, price, qty }

  var cartDrawer = document.getElementById("cart-drawer");
  var overlay = document.getElementById("overlay");
  var cartToggle = document.getElementById("cart-toggle");
  var cartClose = document.getElementById("cart-close");
  var cartItemsEl = document.getElementById("cart-items");
  var cartEmptyEl = document.getElementById("cart-empty");
  var cartSubtotalEl = document.getElementById("cart-subtotal");
  var cartCountEl = document.getElementById("cart-count");
  var checkoutBtn = document.getElementById("checkout-btn");

  function openCart() {
    cartDrawer.classList.add("is-open");
    overlay.classList.add("is-visible");
    cartDrawer.setAttribute("aria-hidden", "false");
  }
  function closeCart() {
    cartDrawer.classList.remove("is-open");
    overlay.classList.remove("is-visible");
    cartDrawer.setAttribute("aria-hidden", "true");
  }
  cartToggle.addEventListener("click", openCart);
  cartClose.addEventListener("click", closeCart);
  overlay.addEventListener("click", closeCart);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeCart();
  });

  function formatEuro(n) {
    return (
      "€ " +
      n.toLocaleString("it-IT", { minimumFractionDigits: 0, maximumFractionDigits: 2 })
    );
  }

  function addToCart(name, price) {
    var existing = cart.find(function (i) { return i.name === name; });
    if (existing) {
      existing.qty += 1;
    } else {
      cart.push({ name: name, price: price, qty: 1 });
    }
    renderCart();
    showToast(name + " aggiunto al carrello");
    openCart();
  }

  function removeFromCart(name) {
    cart = cart.filter(function (i) { return i.name !== name; });
    renderCart();
  }

  function changeQty(name, delta) {
    var item = cart.find(function (i) { return i.name === name; });
    if (!item) return;
    item.qty += delta;
    if (item.qty <= 0) {
      removeFromCart(name);
      return;
    }
    renderCart();
  }

  function renderCart() {
    cartItemsEl.innerHTML = "";

    if (cart.length === 0) {
      cartItemsEl.appendChild(cartEmptyEl);
      cartCountEl.hidden = true;
    } else {
      var totalQty = 0;
      var subtotal = 0;

      cart.forEach(function (item) {
        totalQty += item.qty;
        subtotal += item.qty * item.price;

        var row = document.createElement("div");
        row.className = "cart-item";
        row.innerHTML =
          '<div class="cart-item-media">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"/></svg>' +
          "</div>" +
          '<div class="cart-item-body">' +
          "<h4>" + item.name + "</h4>" +
          '<div class="cart-item-price">' + formatEuro(item.price * item.qty) + "</div>" +
          '<div class="qty-control">' +
          '<button type="button" data-action="dec" aria-label="Diminuisci quantità"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg></button>' +
          '<span>' + item.qty + '</span>' +
          '<button type="button" data-action="inc" aria-label="Aumenta quantità"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>' +
          "</div>" +
          '<button type="button" class="cart-item-remove" data-action="remove">Rimuovi</button>' +
          "</div>";

        row.querySelector('[data-action="dec"]').addEventListener("click", function () {
          changeQty(item.name, -1);
        });
        row.querySelector('[data-action="inc"]').addEventListener("click", function () {
          changeQty(item.name, 1);
        });
        row.querySelector('[data-action="remove"]').addEventListener("click", function () {
          removeFromCart(item.name);
        });

        cartItemsEl.appendChild(row);
      });

      cartCountEl.hidden = false;
      cartCountEl.textContent = String(totalQty);
      cartSubtotalEl.textContent = formatEuro(subtotal);
      return;
    }

    cartSubtotalEl.textContent = formatEuro(0);
  }

  document.querySelectorAll(".add-to-cart").forEach(function (btn) {
    btn.addEventListener("click", function () {
      addToCart(btn.dataset.name, parseFloat(btn.dataset.price));
    });
  });

  checkoutBtn.addEventListener("click", function () {
    if (cart.length === 0) {
      showToast("Il carrello è vuoto");
      return;
    }
    showToast("Demo: il pagamento reale (carta / PayPal / Scalapay) sarà collegato in seguito.");
  });

  renderCart();

  /* ---------- Demo forms ---------- */
  function wireDemoForm(formId, successId) {
    var form = document.getElementById(formId);
    var success = document.getElementById(successId);
    if (!form) return;
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }
      success.classList.add("is-visible");
      form.reset();
    });
  }
  wireDemoForm("reseller-form", "reseller-success");
  wireDemoForm("contact-form", "contact-success");

  /* ---------- Chat assistant ---------- */
  var chatToggle = document.getElementById("chat-toggle");
  var chatPanel = document.getElementById("chat-panel");
  var chatMessages = document.getElementById("chat-messages");
  var chatForm = document.getElementById("chat-form");
  var chatInput = document.getElementById("chat-input");
  var chatHistory = [];
  var chatBusy = false;

  function chatOpen() {
    chatPanel.classList.add("is-open");
    chatToggle.classList.add("is-open");
    chatPanel.setAttribute("aria-hidden", "false");
    chatInput.focus();
  }
  function chatClose() {
    chatPanel.classList.remove("is-open");
    chatToggle.classList.remove("is-open");
    chatPanel.setAttribute("aria-hidden", "true");
  }
  chatToggle.addEventListener("click", function () {
    if (chatPanel.classList.contains("is-open")) chatClose();
    else chatOpen();
  });

  function addChatMessage(text, who) {
    var el = document.createElement("div");
    el.className = "chat-msg chat-msg-" + who;
    el.textContent = text;
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return el;
  }

  function showTyping() {
    var el = document.createElement("div");
    el.className = "chat-msg-typing";
    el.id = "chat-typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  function hideTyping() {
    var el = document.getElementById("chat-typing");
    if (el) el.remove();
  }

  chatForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = chatInput.value.trim();
    if (!text || chatBusy) return;

    addChatMessage(text, "user");
    chatInput.value = "";
    chatBusy = true;
    showTyping();

    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: chatHistory.slice(-8) }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        hideTyping();
        var reply = data.reply || "Mi dispiace, non ho una risposta al momento.";
        addChatMessage(reply, "bot");
        chatHistory.push({ role: "user", content: text });
        chatHistory.push({ role: "assistant", content: reply });
      })
      .catch(function () {
        hideTyping();
        addChatMessage("Connessione non riuscita. Riprova tra poco o scrivi a info@wolman.it.", "bot");
      })
      .finally(function () {
        chatBusy = false;
      });
  });
})();
