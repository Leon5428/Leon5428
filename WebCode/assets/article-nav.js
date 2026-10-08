/* Keep the local outline in sync with the section being read. */
(() => {
    const links = [...document.querySelectorAll(".toc-list a[href^='#']")];
    const entries = links.map(link => ({
        link, heading: document.getElementById(decodeURIComponent(link.hash.slice(1)))
    })).filter(entry => entry.heading);
    if (!entries.length) return;
    let scheduled = false;
    let activeLink = null;
    function update() {
        scheduled = false;
        let current = entries[0];
        const threshold = Math.min(160, window.innerHeight * 0.25);
        for (const entry of entries) {
            if (entry.heading.getBoundingClientRect().top <= threshold) current = entry;
        }
        if (window.scrollY > 0 &&
            window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
            current = entries[entries.length - 1];
        }
        const changed = activeLink !== current.link;
        activeLink = current.link;
        for (const entry of entries) {
            if (entry === current) entry.link.setAttribute("aria-current", "location");
            else entry.link.removeAttribute("aria-current");
        }
        const sidebar = current.link.closest(".toc-sidebar");
        if (changed && getComputedStyle(sidebar).position === "sticky") {
            const item = current.link.getBoundingClientRect();
            const bounds = sidebar.getBoundingClientRect();
            if (item.top < bounds.top || item.bottom > bounds.bottom) {
                sidebar.scrollTop += item.top - bounds.top - bounds.height / 2;
            }
        }
    }
    function schedule() {
        if (!scheduled) {
            scheduled = true;
            requestAnimationFrame(update);
        }
    }
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("hashchange", schedule);
    window.addEventListener("load", schedule);
    if ("ResizeObserver" in window) {
        new ResizeObserver(schedule).observe(document.querySelector(".article-body"));
    }
    update();
})();
