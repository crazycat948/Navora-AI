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
  const token = localStorage.getItem("token");

  if (!token) {
    alert("Please log in first.");
    window.location.href = "login.html";
    return;
  }

  const departureCity = document.getElementById("departure_city").value.trim();
  const destinationCity = document.getElementById("destination_city").value.trim();

  if (departureCity.toLowerCase() === destinationCity.toLowerCase()) {
    alert("Departure city and destination city must be different.");
    return;
  }

  const tripData = {
    title: document.getElementById("title").value,
    destination_city: destinationCity,
    departure_city: departureCity,
    arrival_date: document.getElementById("arrival_date").value,
    departure_date: document.getElementById("departure_date").value,
    traveler_type: document.getElementById("traveler_type").value,
    budget: Number(document.getElementById("budget").value),
    has_car: document.getElementById("has_car").checked,
    need_hotel: document.getElementById("need_hotel").checked,
    need_flight: document.getElementById("need_flight").checked
  };

  const createRes = await fetch(`${API_BASE}/api/trips/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify(tripData)
  });

  const createData = await createRes.json();

  if (!createRes.ok || !createData.trip_id) {
    alert(createData.detail || "Failed to create trip.");
    return;
  }

  const tripId = createData.trip_id;
  document.getElementById("trip_id").value = tripId;

  showLoader();
  setLoading("Generating AI itinerary...");

  try {
    const genRes = await fetch(`${API_BASE}/api/trips/${tripId}/generate-ai-itinerary`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    });

    const genData = await genRes.json();
    showOutput(genData);

    if (tripData.need_hotel || tripData.need_flight) {
      setLoading("Generating hotel & flight recommendations...");
      await fetch(`${API_BASE}/api/trips/${tripId}/travel-recommendations`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
    }

    await getTripDetail();
  } finally {
    clearLoader();
    clearLoading();
  }
}

let dotsInterval = null;

function showLoader() {
  document.getElementById("tripDetail").innerHTML = `
    <div class="empty-state">
      <div class="bounce-loader">
        <span class="bounce-ball"></span>
        <span class="bounce-ball"></span>
        <span class="bounce-ball"></span>
        <span class="bounce-ball"></span>
        <span class="bounce-ball"></span>
      </div>
      <p class="loader-hint">Generating your itinerary may take one to two minutes<span id="loader-dots"></span></p>
    </div>
  `;

  let count = 0;
  dotsInterval = setInterval(() => {
    const el = document.getElementById("loader-dots");
    if (!el) { clearInterval(dotsInterval); return; }
    count = count >= 6 ? 0 : count + 1;
    el.textContent = ".".repeat(count);
  }, 400);
}

function clearLoader() {
  if (dotsInterval) {
    clearInterval(dotsInterval);
    dotsInterval = null;
  }
}

async function generateAIItinerary() {
  const tripId = document.getElementById("trip_id").value;

  showLoader();
  setLoading("Generating AI itinerary...");

  try {
    const res = await fetch(`${API_BASE}/api/trips/${tripId}/generate-ai-itinerary`, {
      method: "POST"
    });

    const data = await res.json();
    showOutput(data);

    await getTripDetail();
  } finally {
    clearLoader();
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

  const [tripRes, weatherRes] = await Promise.all([
    fetch(`${API_BASE}/api/trips/${tripId}`),
    fetch(`${API_BASE}/api/trips/${tripId}/weather`)
  ]);

  const data = await tripRes.json();
  const weatherData = await weatherRes.json();

  const weatherMap = {};
  if (weatherData.daily_recommendations) {
    weatherData.daily_recommendations.forEach(d => {
      weatherMap[d.date] = d.weather_type;
    });
  }

  showOutput(data);
  renderTripDetail(data, weatherMap);
}

const WEATHER_EMOJI = {
  sunny: "☀️",
  rainy: "🌧️",
  cloudy: "⛅",
};

function cardHTML(item, weatherEmoji = "") {
  const typeClass = item.item_type === "restaurant" ? "restaurant" : "attraction";
  const typeLabel = item.item_type === "restaurant" ? "🍽 Restaurant" : "🏛 Attraction";
  const lockBadge = item.locked ? '<span class="lock-badge">🔒</span>' : "";
  const time = `${item.start_time.slice(0,5)} – ${item.end_time.slice(0,5)}`;
  const weatherSpan = weatherEmoji ? `<span class="weather-emoji">${weatherEmoji}</span>` : "";

  return `
    <div class="card-top">
      <span class="type-badge ${typeClass}">${typeLabel}</span>
      <span class="card-name">${item.name}</span>
      ${weatherSpan}<span class="time-badge">${time}</span>
      ${lockBadge}
    </div>
    <p class="card-address">📍 ${item.address}</p>
    <p class="card-notes">${item.notes}</p>
    <div class="card-edit">
      <input class="card-input" id="start_${item.id}" type="time" value="${item.start_time.slice(0,5)}">
      <input class="card-input" id="end_${item.id}" type="time" value="${item.end_time.slice(0,5)}">
      <input class="card-input" id="notes_${item.id}" placeholder="Notes" value="${item.notes}">
    </div>
    <div class="card-actions">
      <button class="btn btn-success btn-sm" onclick="updateItem(${item.id})">Save</button>
      ${item.locked ? "" : `<button class="btn btn-outline btn-sm" onclick="replaceItem(${item.id})">Replace</button>`}
      ${item.locked
        ? `<button class="btn btn-warning btn-sm" onclick="unlockItem(${item.id})">Unlock</button>`
        : `<button class="btn btn-warning btn-sm" onclick="lockItem(${item.id})">Lock</button>`}
      ${item.locked ? "" : `<button class="btn btn-danger btn-sm" onclick="deleteItem(${item.id})">Delete</button>`}
    </div>
  `;
}

function renderTripDetail(data, weatherMap = {}) {
  const container = document.getElementById("tripDetail");
  container.innerHTML = "";

  if (!data.days) {
    container.innerHTML = "<p>No itinerary found.</p>";
    return;
  }

  const header = document.createElement("div");
  header.className = "trip-header";
  header.innerHTML = `<h1 class="trip-title">${data.trip.title}</h1>`;
  container.appendChild(header);

  data.days.forEach(day => {
    const dayDiv = document.createElement("div");
    dayDiv.className = "day-block";

    const weatherType = weatherMap[day.date] || "";
    const weatherEmoji = WEATHER_EMOJI[weatherType] || "";

    dayDiv.innerHTML = `
      <div class="day-header">
        <span class="day-number-badge">Day ${day.day_number}</span>
        <span class="day-theme">${day.theme}</span>
        <span class="day-date">${weatherEmoji} ${day.date}</span>
      </div>
    `;

    const sortedItems = [...day.items].sort((a, b) =>
      a.start_time.localeCompare(b.start_time)
    );

    sortedItems.forEach(item => {
      const card = document.createElement("div");
      card.id = `card_${item.id}`;
      card.className = `item-card${item.locked ? " locked" : ""}`;
      card.innerHTML = cardHTML(item, weatherEmoji);
      dayDiv.appendChild(card);
    });

    const addBtn = document.createElement("button");
    addBtn.className = "btn btn-outline btn-sm add-attraction-btn";
    addBtn.textContent = "+ Add Attraction";
    addBtn.onclick = () => addAttractionToDay(day.id, data.trip.id, dayDiv, weatherEmoji);
    dayDiv.appendChild(addBtn);

    container.appendChild(dayDiv);
  });

  if (data.hotels && data.hotels.length > 0) {
    const hotelSection = document.createElement("div");
    hotelSection.className = "rec-section";
    hotelSection.innerHTML = `<p class="rec-section-title">🏨 Hotel Recommendations</p>`;

    data.hotels.forEach(hotel => {
      const card = document.createElement("div");
      card.className = "rec-card";
      card.innerHTML = `
        <p class="rec-card-title">${hotel.hotel_name}</p>
        <p class="rec-card-row">📍 ${hotel.address}</p>
        <p class="rec-card-row">💰 $${hotel.price_estimate} &nbsp;·&nbsp; ⭐ ${hotel.rating}</p>
        <p class="rec-card-row">${hotel.notes}</p>
      `;
      hotelSection.appendChild(card);
    });

    container.appendChild(hotelSection);
  }

  if (data.flights && data.flights.length > 0) {
    const flightSection = document.createElement("div");
    flightSection.className = "rec-section";
    flightSection.innerHTML = `<p class="rec-section-title">✈️ Flight Recommendations</p>`;

    data.flights.forEach(flight => {
      const card = document.createElement("div");
      card.className = "rec-card";
      card.innerHTML = `
        <p class="rec-card-title">${flight.airline}</p>
        <p class="rec-card-row">🛫 ${flight.departure_airport} → ${flight.arrival_airport}</p>
        <p class="rec-card-row">🕐 ${flight.departure_time} → ${flight.arrival_time}</p>
        <p class="rec-card-row">💰 $${flight.price_estimate}</p>
        <p class="rec-card-row">${flight.notes}</p>
      `;
      flightSection.appendChild(card);
    });

    container.appendChild(flightSection);
  }
}

async function updateItem(itemId) {
  const newStart = document.getElementById(`start_${itemId}`).value;
  const newEnd = document.getElementById(`end_${itemId}`).value;

  if (newStart >= newEnd) {
    alert("End time must be after start time.");
    return;
  }

  const card = document.getElementById(`card_${itemId}`);
  const dayBlock = card.closest(".day-block");
  const otherCards = dayBlock.querySelectorAll(".item-card");

  for (const other of otherCards) {
    const otherId = other.id.replace("card_", "");
    if (parseInt(otherId) === itemId) continue;
    const otherStart = document.getElementById(`start_${otherId}`)?.value;
    const otherEnd = document.getElementById(`end_${otherId}`)?.value;
    if (!otherStart || !otherEnd) continue;
    if (newStart < otherEnd && otherStart < newEnd) {
      const otherName = other.querySelector(".card-name")?.textContent || `item ${otherId}`;
      alert(`Time conflict with "${otherName}" (${otherStart}–${otherEnd}). Please adjust the time.`);
      return;
    }
  }

  setLoading(`Updating item ${itemId}...`);

  const updateData = {
    start_time: newStart,
    end_time: newEnd,
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
    const dayBlock = document.getElementById(`card_${itemId}`)?.closest(".day-block");
    if (dayBlock) resortDayBlock(dayBlock);
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

function resortDayBlock(dayBlock) {
  const addBtn = dayBlock.querySelector(".add-attraction-btn");
  const cards = [...dayBlock.querySelectorAll(".item-card")];

  cards.sort((a, b) => {
    const aStart = document.getElementById(`start_${a.id.replace("card_", "")}`)?.value || "";
    const bStart = document.getElementById(`start_${b.id.replace("card_", "")}`)?.value || "";
    return aStart.localeCompare(bStart);
  });

  cards.forEach(card => dayBlock.insertBefore(card, addBtn));
}

function updateSingleCard(updatedItem) {
  const card = document.getElementById(`card_${updatedItem.id}`);
  if (!card) return;

  card.className = `item-card${updatedItem.locked ? " locked" : ""}`;
  card.innerHTML = cardHTML(updatedItem);
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locked: true })
    });

    const data = await res.json();
    showOutput(data);
    updateSingleCard(data.item);
  } finally {
    clearLoading();
  }
}

async function unlockItem(itemId) {
  setLoading(`Unlocking item ${itemId}...`);

  try {
    const res = await fetch(`${API_BASE}/api/itinerary-items/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locked: false })
    });

    const data = await res.json();
    showOutput(data);
    updateSingleCard(data.item);
  } finally {
    clearLoading();
  }
}

async function addAttractionToDay(dayId, tripId, dayDiv, weatherEmoji) {
  setLoading("Generating new attraction...");

  try {
    const res = await fetch(`${API_BASE}/api/trips/${tripId}/days/${dayId}/add-attraction`, {
      method: "POST"
    });

    const data = await res.json();
    showOutput(data);

    const item = data.item;
    const card = document.createElement("div");
    card.id = `card_${item.id}`;
    card.className = "item-card";
    card.innerHTML = cardHTML(item, weatherEmoji);

    const addBtn = dayDiv.querySelector(".add-attraction-btn");
    dayDiv.insertBefore(card, addBtn);
  } finally {
    clearLoading();
  }
}
