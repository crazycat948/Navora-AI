function setupCityAutocomplete(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;

  const dropdown = document.createElement("div");
  dropdown.className = "city-dropdown";

  input.parentNode.style.position = "relative";
  input.parentNode.appendChild(dropdown);

  let debounceTimer = null;

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const q = input.value.trim();

    if (q.length < 2) {
      dropdown.innerHTML = "";
      dropdown.style.display = "none";
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/cities/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();

        dropdown.innerHTML = "";

        if (!data.cities || data.cities.length === 0) {
          dropdown.style.display = "none";
          return;
        }

        data.cities.forEach(city => {
          const item = document.createElement("div");
          item.className = "city-dropdown-item";
          item.textContent = city.label;
          item.addEventListener("mousedown", () => {
            input.value = city.name;
            dropdown.innerHTML = "";
            dropdown.style.display = "none";
          });
          dropdown.appendChild(item);
        });

        dropdown.style.display = "block";
      } catch (e) {
        dropdown.style.display = "none";
      }
    }, 300);
  });

  input.addEventListener("blur", () => {
    setTimeout(() => {
      dropdown.style.display = "none";
    }, 150);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dropdown.style.display = "none";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupCityAutocomplete("departure_city");
  setupCityAutocomplete("destination_city");
});
