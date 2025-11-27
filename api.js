/**
 * Dashboard initialization and utilities
 * Firebase-based database operations
 */

// Wait for Firebase initialization
function waitForFirebaseDB() {
	return new Promise(resolve => {
		const checkFirebase = setInterval(() => {
			if (typeof firebaseDB !== 'undefined') {
				clearInterval(checkFirebase);
				resolve();
			}
		}, 100);
		setTimeout(() => {
			clearInterval(checkFirebase);
			resolve();
		}, 5000);
	});
}

// Initialize dashboard on page load
async function initializeDashboard() {
	await waitForFirebaseDB();

	// Check if user is logged in
	firebaseDB.onAuthStateChanged(user => {
		if (!user) {
			window.location.href = 'login.html';
			return;
		}

		// Load dashboard stats
		loadDashboardStats();

		// Load recent decks
		loadRecentDecks();
	});
}

// Load collection and deck statistics
async function loadDashboardStats() {
	try {
		// Get current user
		const user = await firebaseDB.getCurrentUser();
		if (!user) return;

		// Load collection cards
		const cards = await firebaseDB.getCollectionCards();
		const totalCards = cards.reduce((sum, card) => sum + (card.quantity || 1), 0);
		const uniqueCards = new Set(cards.map(c => c.name)).size;

		// Update dashboard elements
		const totalEl = document.getElementById('totalCards');
		const uniqueEl = document.getElementById('uniqueCards');
		if (totalEl) totalEl.textContent = totalCards || 0;
		if (uniqueEl) uniqueEl.textContent = uniqueCards || 0;

		console.log(`Dashboard: ${totalCards} total cards, ${uniqueCards} unique`);
	} catch (error) {
		console.error('Error loading dashboard stats:', error);
	}
}

// Load recent decks
async function loadRecentDecks() {
	try {
		const decks = await firebaseDB.getDecks();
		if (!Array.isArray(decks) || decks.length === 0) {
			console.log('No decks found');
			return;
		}

		// Show recent section and populate with decks
		const recentSection = document.getElementById('recentDecks');
		const decksList = document.getElementById('decksList');

		if (!recentSection || !decksList) {
			console.warn('Dashboard deck elements not found');
			return;
		}

		recentSection.style.display = 'block';

		// Display up to 6 recent decks
		const html = decks.slice(0, 6).map(deck => `
			<article>
				<a href="deckbuilding.html?deck=${encodeURIComponent(deck.id)}" class="image" style="background:#333; display:flex; align-items:center; justify-content:center; color:#999;">
					<span class="icon solid fa-layer-group" style="font-size:3em;"></span>
				</a>
				<h3>${deck.name || 'Unnamed Deck'}</h3>
				<p>${deck.deckType || 'Standard'} • ${(deck.cards && deck.cards.length) || 0} cards${deck.commander ? ` • ${deck.commander}` : ''}</p>
				<ul class="actions">
					<li><a href="deckbuilding.html?deck=${encodeURIComponent(deck.id)}" class="button small">View Deck</a></li>
				</ul>
			</article>
		`).join('');

		decksList.innerHTML = html;
		console.log(`Loaded ${decks.length} decks`);
	} catch (error) {
		console.error('Error loading recent decks:', error);
	}
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeDashboard);
