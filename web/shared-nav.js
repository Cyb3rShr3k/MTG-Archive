// shared-nav.js - Common navigation and sidebar for all pages
const sharedNav = {
    sidebar: `
        <!-- Sidebar -->
        <div id="sidebar">
            <div class="inner">

                <!-- Search -->
                <section id="search" class="alt">
                    <form id="quickSearchForm">
                        <input type="text" name="query" id="quickSearch" placeholder="Quick card search..." />
                    </form>
                    <div id="searchResults" style="margin-top:1em; display:none; max-height:300px; overflow-y:auto;"></div>
                </section>

                <!-- Menu -->
                <nav id="menu">
                    <header class="major">
                        <h2>Menu</h2>
                    </header>
                    <ul>
                        <li><a href="index.html" class="nav-home">Dashboard</a></li>
                        <li><a href="card_addition.html" class="nav-add">Add Cards</a></li>
                        <li><a href="deckbuilding.html" class="nav-decks">Deck Building</a></li>
                        <li>
                            <span class="opener">Import</span>
                            <ul>
                                <li><a href="card_addition.html#csv">CSV Import</a></li>
                                <li><a href="card_addition.html#scan">OCR Scanner</a></li>
                                <li><a href="deckbuilding.html#precon">Precon Decks</a></li>
                            </ul>
                        </li>
                        <li>
                            <span class="opener">Collection</span>
                            <ul>
                                <li><a href="deckbuilding.html#search">Browse Cards</a></li>
                                <li><a href="deckbuilding.html#stats">Statistics</a></li>
                                <li><a href="deckbuilding.html#export">Export Data</a></li>
                            </ul>
                        </li>
                        <li>
                            <span class="opener">Account</span>
                            <ul id="accountMenu">
                                <li><a href="login.html" id="menuLogin">Login</a></li>
                                <li><a href="register.html" id="menuRegister">Register</a></li>
                                <li><a href="#" id="menuLogout" style="display:none;">Logout</a></li>
                            </ul>
                        </li>
                    </ul>
                </nav>

                <!-- Collection Summary -->
                <section>
                    <header class="major">
                        <h2>Collection</h2>
                    </header>
                    <div id="collectionSummary">
                        <p style="color:#999; font-size:0.9em;">Loading...</p>
                    </div>
                </section>

                <!-- Footer -->
                <footer id="footer">
                    <p class="copyright">&copy; MTG Archive by RB Labs.<br>
                    <a href="https://www.buymeacoffee.com/yourusername" target="_blank" style="color:#f56a6a;">☕ Support</a><br>
                    Design: <a href="https://html5up.net">HTML5 UP</a></p>
                </footer>

            </div>
        </div>`,

    header: (pageTitle = 'MTG Archive') => `
        <!-- Header -->
        <header id="header">
            <a href="index.html" class="logo"><strong>MTG Archive</strong> by RB Labs</a>
            <ul class="icons">
                <li><span id="userDisplay" style="margin-right: 1em; color: #999; font-size:0.9em;"></span></li>
                <li><a href="#" id="btnLogout" class="button small" style="display:none;">Logout</a></li>
            </ul>
        </header>`,

    // Initialize sidebar and shared functionality
    init: async function() {
        // Load collection summary in sidebar
        try {
            const total = await window.pywebview.api.get_collection_count();
            const decks = await window.pywebview.api.list_decks();
            const collection = await window.pywebview.api.search_collection({ query: '', filters: {} });
            
            const uniqueNames = new Set();
            if (Array.isArray(collection)) {
                collection.forEach(card => uniqueNames.add(card.name));
            }

            const summary = document.getElementById('collectionSummary');
            if (summary) {
                summary.innerHTML = `
                    <ul class="alt" style="margin:0; padding:0; list-style:none;">
                        <li style="padding:0.5em 0; border-bottom:1px solid rgba(210,215,217,0.15);">
                            <strong style="color:#f56a6a;">${total || 0}</strong> <span style="color:#999;">total cards</span>
                        </li>
                        <li style="padding:0.5em 0; border-bottom:1px solid rgba(210,215,217,0.15);">
                            <strong style="color:#4c84ff;">${uniqueNames.size}</strong> <span style="color:#999;">unique</span>
                        </li>
                        <li style="padding:0.5em 0;">
                            <strong style="color:#39c088;">${Array.isArray(decks) ? decks.length : 0}</strong> <span style="color:#999;">decks</span>
                        </li>
                    </ul>
                    <ul class="actions" style="margin-top:1em;">
                        <li><a href="card_addition.html" class="button small primary fit">Add Cards</a></li>
                    </ul>
                `;
            }
        } catch (error) {
            console.error('Failed to load collection summary:', error);
        }

        // Check user login status
        try {
            const userInfo = await window.pywebview.api.current_user();
            if (userInfo.logged_in) {
                const user = userInfo.user;
                document.getElementById('userDisplay').textContent = `${user.username}`;
                document.getElementById('btnLogout').style.display = 'inline-block';
                document.getElementById('menuLogout').style.display = 'block';
                document.getElementById('menuLogin').style.display = 'none';
                document.getElementById('menuRegister').style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to check user status:', error);
        }

        // Quick search functionality
        const quickSearchForm = document.getElementById('quickSearchForm');
        if (quickSearchForm) {
            quickSearchForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const query = document.getElementById('quickSearch').value;
                if (!query.trim()) return;

                try {
                    const results = await window.pywebview.api.search_cards({ query, limit: 10 });
                    const resultsDiv = document.getElementById('searchResults');
                    
                    if (results && results.length > 0) {
                        resultsDiv.innerHTML = results.map(card => 
                            `<div style="padding:0.5em; background:rgba(0,0,0,0.2); margin-bottom:0.5em; border-radius:4px; font-size:0.85em;">
                                ${card}
                            </div>`
                        ).join('');
                        resultsDiv.style.display = 'block';
                    } else {
                        resultsDiv.innerHTML = '<p style="color:#999; font-size:0.85em;">No results</p>';
                        resultsDiv.style.display = 'block';
                    }
                } catch (error) {
                    console.error('Search error:', error);
                }
            });
        }

        // Logout handlers
        async function logout() {
            try {
                await window.pywebview.api.logout();
                window.location.href = 'login.html';
            } catch (error) {
                console.error('Logout error:', error);
                window.location.href = 'login.html';
            }
        }

        const btnLogout = document.getElementById('btnLogout');
        const menuLogout = document.getElementById('menuLogout');
        if (btnLogout) btnLogout.addEventListener('click', (e) => { e.preventDefault(); logout(); });
        if (menuLogout) menuLogout.addEventListener('click', (e) => { e.preventDefault(); logout(); });

        // Highlight current page in menu
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        document.querySelectorAll('#menu a').forEach(link => {
            if (link.getAttribute('href') === currentPage) {
                link.style.color = '#f56a6a';
                link.style.fontWeight = 'bold';
            }
        });
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => sharedNav.init());
} else {
    sharedNav.init();
}
