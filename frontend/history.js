requireLogin();

async function loadTripHistory() {
  const token = localStorage.getItem("token");

  const res = await fetch(`${API_BASE}/api/trips`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${token}`
    }
  });

  const data = await res.json();

  if (!res.ok) {
    alert(data.detail || "Failed to load trip history");
    return;
  }

  renderTripHistory(data.trips);
}

function renderTripHistory(trips) {
  const container = document.getElementById("historyList");
  container.innerHTML = "";

  if (!trips || trips.length === 0) {
    container.innerHTML = "<p>No trips found.</p>";
    return;
  }

  trips.forEach(trip => {
    const card = document.createElement("div");
    card.className = "history-card";

    card.innerHTML = `
      <p class="history-card-title">${trip.title}</p>
      <p class="history-card-row">📍 <span>${trip.destination_city}</span> from ${trip.departure_city}</p>
      <p class="history-card-row">📅 <span>${trip.arrival_date}</span> → <span>${trip.departure_date}</span></p>
      <p class="history-card-row">🧳 <span>${trip.traveler_type}</span> &nbsp;·&nbsp; 💰 <span>$${trip.budget}</span></p>
      <button class="btn btn-danger btn-sm" style="margin-top:12px;" onclick="event.stopPropagation(); deleteTrip(${trip.id});">Delete</button>
    `;

    card.onclick = () => {
      localStorage.setItem("selectedTripId", trip.id);
      window.location.href = "trip-detail.html";
    };

    container.appendChild(card);
  });
}

async function deleteTrip(tripId) {
  const token = localStorage.getItem("token");

  const confirmed = confirm("Are you sure you want to delete this trip?");

  if (!confirmed) return;

  const res = await fetch(`${API_BASE}/api/trips/${tripId}`, {
    method: "DELETE",
    headers: {
      "Authorization": `Bearer ${token}`
    }
  });

  const data = await res.json();

  if (!res.ok) {
    alert(data.detail || "Failed to delete trip");
    return;
  }

  loadTripHistory();
}

loadTripHistory();
