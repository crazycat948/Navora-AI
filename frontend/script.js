const API_BASE = "http://127.0.0.1:8000";

function showOutput(data) {
  document.getElementById("output").textContent = JSON.stringify(data, null, 2);
}

function setLoading(message) {
  document.getElementById("loading").textContent = message;
}

function clearLoading() {
  document.getElementById("loading").textContent = "";
}

async function createTrip() {
  const tripData = {
    title: document.getElementById("title").value,
    destination_city: document.getElementById("destination_city").value,
    departure_city: document.getElementById("departure_city").value,
    arrival_date: document.getElementById("arrival_date").value,
    departure_date: document.getElementById("departure_date").value,
    traveler_type: document.getElementById("traveler_type").value,
    budget: Number(document.getElementById("budget").value),
    has_car: document.getElementById("has_car").checked,
    need_hotel: document.getElementById("need_hotel").checked,
    need_flight: document.getElementById("need_flight").checked
  };

  const res = await fetch(`${API_BASE}/api/trips/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(tripData)
  });

  const data = await res.json();
  showOutput(data);

  if (data.trip_id) {
    document.getElementById("trip_id").value = data.trip_id;
  }
}

async function generateAIItinerary() {
  const tripId = document.getElementById("trip_id").value;

  setLoading("Generating AI itinerary...");

  try {
    const res = await fetch(`${API_BASE}/api/trips/${tripId}/generate-ai-itinerary`, {
      method: "POST"
    });

    const data = await res.json();
    showOutput(data);

    await getTripDetail();
  } finally {
    clearLoading();
  }
}

async function getTripHistory() {
  const res = await fetch(`${API_BASE}/api/trips`);
  const data = await res.json();
  showOutput(data);
}

async function getTripDetail() {
  const tripId = document.getElementById("trip_id").value;

  const res = await fetch(`${API_BASE}/api/trips/${tripId}`);
  const data = await res.json();

  showOutput(data);
  renderTripDetail(data);
}

function renderTripDetail(data) {
  const container = document.getElementById("tripDetail");
  container.innerHTML = "";

  if (!data.days) {
    container.innerHTML = "<p>No itinerary found.</p>";
    return;
  }

  const title = document.createElement("h3");
  title.textContent = data.trip.title;
  container.appendChild(title);

  data.days.forEach(day => {
    const dayDiv = document.createElement("div");

    const dayTitle = document.createElement("h3");
    dayTitle.textContent = `Day ${day.day_number} - ${day.date} - ${day.theme}`;
    dayDiv.appendChild(dayTitle);

    day.items.forEach(item => {
      const card = document.createElement("div");
      card.id = `card_${item.id}`;
      card.style.border = "1px solid black";
      card.style.margin = "10px";
      card.style.padding = "10px";

      card.innerHTML = `
        <p><strong>ID:</strong> ${item.id}</p>
        <p><strong>Type:</strong> ${item.item_type}</p>
        <p><strong>Time:</strong> ${item.start_time} - ${item.end_time}</p>
        <p><strong>Name:</strong> ${item.name}</p>
        <p><strong>Address:</strong> ${item.address}</p>
        <p><strong>Notes:</strong> ${item.notes}</p>
        <p><strong>Locked:</strong> ${item.locked}</p>

        <input id="start_${item.id}" placeholder="Start Time" value="${item.start_time.slice(0,5)}">
        <input id="end_${item.id}" placeholder="End Time" value="${item.end_time.slice(0,5)}">
        <input id="notes_${item.id}" placeholder="Notes" value="${item.notes}">
        <br><br>

        <button onclick="updateItem(${item.id})">Update</button>
        <button onclick="replaceItem(${item.id})">Replace</button>
        <button onclick="lockItem(${item.id})">Lock</button>
        <button onclick="deleteItem(${item.id})">Delete</button>
      `;

      dayDiv.appendChild(card);
    });

    container.appendChild(dayDiv);
  });
}

async function updateItem(itemId) {
  setLoading(`Updating item ${itemId}...`);

  const updateData = {
    start_time: document.getElementById(`start_${itemId}`).value,
    end_time: document.getElementById(`end_${itemId}`).value,
    notes: document.getElementById(`notes_${itemId}`).value
  };

  try {
    const res = await fetch(`${API_BASE}/api/itinerary-items/${itemId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(updateData)
    });

    const data = await res.json();
    showOutput(data);
    updateSingleCard(data.item);
  } finally {
    clearLoading();
  }
}

async function replaceItem(itemId) {
  setLoading(`Replacing item ${itemId}...`);

  try {
    const res = await fetch(`${API_BASE}/api/itinerary-items/${itemId}/replace`, {
      method: "POST"
    });

    const data = await res.json();
    showOutput(data);

    updateSingleCard(data.item);
  } finally {
    clearLoading();
  }
}

function updateSingleCard(updatedItem) {
  const card = document.getElementById(`card_${updatedItem.id}`);

  if (!card) return;

  card.innerHTML = `
    <p><strong>ID:</strong> ${updatedItem.id}</p>
    <p><strong>Type:</strong> ${updatedItem.item_type}</p>
    <p><strong>Time:</strong> ${updatedItem.start_time} - ${updatedItem.end_time}</p>
    <p><strong>Name:</strong> ${updatedItem.name}</p>
    <p><strong>Address:</strong> ${updatedItem.address}</p>
    <p><strong>Notes:</strong> ${updatedItem.notes}</p>
    <p><strong>Locked:</strong> ${updatedItem.locked}</p>

    <input id="start_${updatedItem.id}" value="${updatedItem.start_time.slice(0,5)}">
    <input id="end_${updatedItem.id}" value="${updatedItem.end_time.slice(0,5)}">
    <input id="notes_${updatedItem.id}" value="${updatedItem.notes}">
    <br><br>

    <button onclick="updateItem(${updatedItem.id})">Update</button>
    <button onclick="replaceItem(${updatedItem.id})">Replace</button>
    <button onclick="lockItem(${updatedItem.id})">Lock</button>
    <button onclick="deleteItem(${updatedItem.id})">Delete</button>
  `;
}

async function deleteItem(itemId) {
  setLoading(`Deleting item ${itemId}...`);

  try {
    const res = await fetch(`${API_BASE}/api/itinerary-items/${itemId}`, {
      method: "DELETE"
    });

    const data = await res.json();
    showOutput(data);

    const card = document.getElementById(`card_${itemId}`);
    if (card) {
      card.remove();
    }
  } finally {
    clearLoading();
  }
}

async function lockItem(itemId) {
  setLoading(`Locking item ${itemId}...`);

  try {
    const res = await fetch(`${API_BASE}/api/itinerary-items/${itemId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        locked: true
      })
    });

    const data = await res.json();
    showOutput(data);
    updateSingleCard(data.item);
  } finally {
    clearLoading();
  }
}
