(() => {
  // Menu mobile
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".site-nav");
  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    nav.classList.toggle("is-open", open);
    toggle.querySelector("use").setAttribute("href", open ? "#i-x" : "#i-menu");
    toggle.querySelector(".nav-toggle__label").textContent = open ? "Fermer" : "Menu";
  };
  toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
  nav.addEventListener("click", (event) => {
    if (event.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setOpen(false);
      toggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".site-header")) setOpen(false);
  });

  // Agrandissement des captures ; sans script, le lien ouvre simplement l'image.
  const dialog = document.querySelector(".lightbox");
  const large = dialog.querySelector("img");
  const caption = dialog.querySelector(".lightbox__caption");
  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-lightbox]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    large.src = link.getAttribute("href");
    large.alt = link.querySelector("img").alt;
    caption.textContent = link.dataset.caption;
    dialog.showModal();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });

  // Copie des commandes d'installation, proposée seulement si le navigateur le permet.
  const copy = document.querySelector("[data-copy]");
  if (navigator.clipboard) {
    const status = document.querySelector("[data-copy-status]");
    copy.hidden = false;
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(copy.nextElementSibling.textContent);
        copy.textContent = "Copié";
        status.textContent = "Commandes copiées";
      } catch {
        copy.textContent = "Échec de la copie";
        status.textContent = "La copie a échoué : sélectionnez les commandes manuellement";
      }
      setTimeout(() => {
        copy.textContent = "Copier";
        status.textContent = "";
      }, 2500);
    });
  }

  // Installation du site, proposée uniquement si le navigateur le permet.
  const installBlock = document.querySelector(".pwa-install");
  let installEvent = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installEvent = event;
    installBlock.hidden = false;
  });
  installBlock.querySelector("[data-install]").addEventListener("click", async () => {
    if (!installEvent) return;
    installEvent.prompt();
    await installEvent.userChoice;
    installEvent = null;
    installBlock.hidden = true;
  });
  window.addEventListener("appinstalled", () => {
    installBlock.hidden = true;
  });

  // Service worker : une nouvelle version attend l'accord du visiteur.
  if (!("serviceWorker" in navigator)) return;
  const toast = document.querySelector(".update-toast");
  const offer = (worker) => {
    toast.hidden = false;
    toast.querySelector("[data-reload]").onclick = () => worker.postMessage("skip-waiting");
  };
  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js");
      if (registration.waiting && navigator.serviceWorker.controller) offer(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        worker?.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) offer(worker);
        });
      });
    } catch {
      // Le site reste pleinement utilisable sans service worker.
    }
  });
  let reloading = false;
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloading) return;
    reloading = true;
    window.location.reload();
  });
})();
