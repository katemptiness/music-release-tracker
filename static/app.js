// --- Tab switching ---

const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');

tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        tabButtons.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${tab}`).classList.add('active');

        if (tab === 'feed') loadReleases();
        if (tab === 'artists') loadArtists();
    });
});

// --- Feed Tab ---

const filterArtist = document.getElementById('filter-artist');
const filterType = document.getElementById('filter-type');
const filterUnseen = document.getElementById('filter-unseen');
const releaseList = document.getElementById('release-list');
const unseenBadge = document.getElementById('unseen-badge');

filterArtist.addEventListener('change', loadReleases);
filterType.addEventListener('change', loadReleases);
filterUnseen.addEventListener('change', loadReleases);

async function loadReleases() {
    const params = new URLSearchParams();
    if (filterArtist.value) params.set('artist_id', filterArtist.value);
    if (filterType.value) params.set('type', filterType.value);
    if (filterUnseen.checked) params.set('unseen_only', 'true');

    const resp = await fetch(`/api/releases?${params}`);
    const releases = await resp.json();

    if (releases.length === 0) {
        releaseList.innerHTML = '<p class="empty-state">No releases match your filters.</p>';
    } else {
        releaseList.innerHTML = releases.map(r => `
            <div class="release-item ${r.notified === 0 ? 'unseen' : ''}" data-id="${r.id}">
                <img class="release-cover"
                     src="https://coverartarchive.org/release-group/${esc(r.mbid)}/front-250"
                     alt=""
                     loading="lazy"
                     onerror="this.onerror=null;this.classList.add('no-cover');this.src='/static/icon.svg'">
                <div class="release-info">
                    <div class="release-title">${esc(r.title)}</div>
                    <div class="release-artist">${esc(r.artist_name)}</div>
                    <div class="release-meta">${esc(r.release_type)} · ${esc(r.release_date || 'Unknown date')}</div>
                </div>
                ${r.notified === 0 ? `<span class="release-badge" onclick="markSeen(${r.id}, this)">NEW</span>` : ''}
            </div>
        `).join('');
    }

    updateUnseenBadge();
}

async function markSeen(id, el) {
    await fetch(`/api/releases/${id}/seen`, { method: 'POST' });
    const item = el.closest('.release-item');
    item.classList.remove('unseen');
    el.remove();
    updateUnseenBadge();
}

async function updateUnseenBadge() {
    const resp = await fetch('/api/releases?unseen_only=true');
    const releases = await resp.json();
    const count = releases.length;
    unseenBadge.textContent = count;
    unseenBadge.classList.toggle('hidden', count === 0);
}

// --- Artists Tab ---

const searchInput = document.getElementById('artist-search-input');
const searchBtn = document.getElementById('artist-search-btn');
const searchResults = document.getElementById('search-results');
const artistList = document.getElementById('artist-list');

searchBtn.addEventListener('click', searchArtists);
searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') searchArtists();
});

async function searchArtists() {
    const query = searchInput.value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';

    try {
        const resp = await fetch('/api/artists/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
        });
        const results = await resp.json();

        if (results.length === 0) {
            searchResults.innerHTML = '<p class="status-msg">No artists found.</p>';
        } else {
            searchResults.innerHTML = results.slice(0, 10).map(a => `
                <div class="search-result-item">
                    <div class="result-info">
                        <div class="result-name">${esc(a.name)}</div>
                        <div class="result-detail">
                            ${[a.disambiguation, a.type, a.country].filter(Boolean).join(' · ')}
                        </div>
                    </div>
                    <button class="add-btn" onclick='addArtist(${JSON.stringify(a).replace(/'/g, "&#39;")}, this)'>Add</button>
                </div>
            `).join('');
        }
    } catch (err) {
        searchResults.innerHTML = `<p class="status-msg error">Search failed: ${esc(err.message)}</p>`;
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search';
    }
}

async function addArtist(artist, btn) {
    btn.disabled = true;
    btn.textContent = 'Adding...';

    try {
        const resp = await fetch('/api/artists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mbid: artist.mbid,
                name: artist.name,
                disambiguation: artist.disambiguation,
            }),
        });
        const result = await resp.json();

        if (result.status === 'already_exists') {
            btn.textContent = 'Already added';
        } else {
            btn.textContent = `Added (${result.releases_imported} releases)`;
        }

        loadArtists();
        populateArtistFilter();
    } catch (err) {
        btn.textContent = 'Error';
    }
}

async function loadArtists() {
    const resp = await fetch('/api/artists');
    const artists = await resp.json();

    if (artists.length === 0) {
        artistList.innerHTML = '<p class="empty-state">No artists tracked yet.</p>';
    } else {
        artistList.innerHTML = artists.map(a => `
            <div class="artist-item">
                <div>
                    <span class="artist-name">${esc(a.name)}</span>
                    ${a.disambiguation ? `<span class="artist-disambig"> — ${esc(a.disambiguation)}</span>` : ''}
                </div>
                <button class="remove-btn" onclick="removeArtist(${a.id}, this)">Remove</button>
            </div>
        `).join('');
    }
}

async function removeArtist(id, btn) {
    btn.disabled = true;
    await fetch(`/api/artists/${id}`, { method: 'DELETE' });
    loadArtists();
    populateArtistFilter();
    loadReleases();
}

async function populateArtistFilter() {
    const resp = await fetch('/api/artists');
    const artists = await resp.json();
    const current = filterArtist.value;
    filterArtist.innerHTML = '<option value="">All Artists</option>' +
        artists.map(a => `<option value="${a.id}">${esc(a.name)}</option>`).join('');
    filterArtist.value = current;
}

// --- Check Tab ---

const checkBtn = document.getElementById('check-btn');
const checkProgress = document.getElementById('check-progress');
const checkSummary = document.getElementById('check-summary');

checkBtn.addEventListener('click', runCheck);

function runCheck() {
    checkBtn.disabled = true;
    checkBtn.textContent = 'Checking...';
    checkProgress.innerHTML = '';
    checkSummary.innerHTML = '';

    const source = new EventSource('/api/check');

    source.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'progress') {
            checkProgress.innerHTML = `<p class="progress-line">${esc(data.message)}</p>`;
        } else if (data.type === 'error') {
            checkProgress.innerHTML += `<p class="progress-line error">${esc(data.message)}</p>`;
        } else if (data.type === 'done') {
            source.close();
            checkBtn.disabled = false;
            checkBtn.textContent = 'Check Now';
            checkProgress.innerHTML += `<p class="progress-line" style="color: #03dac6; font-weight: 600;">${esc(data.message)}</p>`;

            if (data.summary && data.summary.length > 0) {
                checkSummary.innerHTML = data.summary.map(s => `
                    <div class="summary-artist">
                        <h3>${esc(s.artist)}</h3>
                        <ul>${s.new_releases.map(r => `<li>${esc(r)}</li>`).join('')}</ul>
                    </div>
                `).join('');
            }

            updateUnseenBadge();
        }
    };

    source.onerror = () => {
        source.close();
        checkBtn.disabled = false;
        checkBtn.textContent = 'Check Now';
        checkProgress.innerHTML += '<p class="progress-line error">Connection lost.</p>';
    };
}

// --- Utilities ---

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// --- Init ---

loadReleases();
populateArtistFilter();
updateUnseenBadge();
