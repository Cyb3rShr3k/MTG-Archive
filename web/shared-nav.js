const sharedNav = {
  header: (title) => `
    <header id="header">
      <a href="index.html" class="logo"><strong>MTG Archive</strong></a>
      <ul class="icons">
        <li><a href="#" onclick="event.preventDefault()" id="userMenuToggle" title="User Menu" style="color:#f56a6a;"><strong id="userDisplay">User</strong></a></li>
      </ul>
    </header>
    <div id="userMenu" style="display:none; position:absolute; top:40px; right:20px; background:#242943; border:1px solid #f56a6a; border-radius:4px; padding:1em; min-width:150px; z-index:1000; box-shadow:0 4px 12px rgba(0,0,0,0.3);">
      <p style="margin:0 0 0.5em 0; color:#f56a6a;"><strong id="userDisplayFull">User</strong></p>
      <p style="margin:0.5em 0; font-size:0.85em; color:#999;" id="userEmailDisplay">email@example.com</p>
      <hr style="border:none; border-top:1px solid #333; margin:0.5em 0;">
      <a href="index.html" style="display:block; padding:0.5em 0; color:#fff; text-decoration:none;">Dashboard</a>
      <a href="card_addition.html" style="display:block; padding:0.5em 0; color:#fff; text-decoration:none;">Add Cards</a>
      <a href="deckbuilding.html" style="display:block; padding:0.5em 0; color:#fff; text-decoration:none;">Build Decks</a>
      <hr style="border:none; border-top:1px solid #333; margin:0.5em 0;">
      <a href="#" onclick="logoutUser(event)" style="display:block; padding:0.5em 0; color:#f56a6a; text-decoration:none;"><strong>Logout</strong></a>
    </div>
  `,

  sidebar: `
    <div id="sidebar">
      <div class="inner">
        <section id="search" class="alt">
          <form onsubmit="searchCollection(event)">
            <input type="text" id="collectionSearch" placeholder="Search collection..." />
          </form>
        </section>

        <nav id="menu">
          <header class="major">
            <h2>Menu</h2>
          </header>
          <ul>
            <li><a href="index.html">Dashboard</a></li>
            <li><a href="card_addition.html">Add Cards</a></li>
            <li><a href="deckbuilding.html">Build Decks</a></li>
            <li>
              <span class="opener" onclick="toggleSubmenu(event)">Collection</span>
              <ul id="collectionMenu" style="display:none;">
                <li><span id="totalCardsMenu">0 Cards</span></li>
                <li><span id="uniqueCardsMenu">0 Unique</span></li>
              </ul>
            </li>
          </ul>
        </nav>

        <section>
          <header class="major">
            <h2>About</h2>
          </header>
          <p>MTG Archive is your personal Magic: The Gathering collection manager. Keep track of your cards, build decks, and organize your collection with ease.</p>
        </section>
      </div>
    </div>
  `
};

// Initialize user menu and auth state
function initializeNav() {
  const userMenuToggle = document.getElementById('userMenuToggle');
  const userMenu = document.getElementById('userMenu');

  if (userMenuToggle) {
    userMenuToggle.addEventListener('click', (e) => {
      e.preventDefault();
      userMenu.style.display = userMenu.style.display === 'none' ? 'block' : 'none';
    });
  }

  // Close menu when clicking elsewhere
  document.addEventListener('click', (e) => {
    if (userMenu && !userMenu.contains(e.target) && e.target !== userMenuToggle) {
      userMenu.style.display = 'none';
    }
  });

  // Check authentication and update user display
  if (typeof firebaseDB !== 'undefined') {
    (async () => {
      try {
        await firebaseDB.onAuthStateChanged(async (user) => {
          if (user) {
            const userInfo = await firebaseDB.getCurrentUserInfo();
            const username = userInfo?.username || user.email.split('@')[0];
            const email = user.email;

            document.getElementById('userDisplay').textContent = username;
            document.getElementById('userDisplayFull').textContent = username;
            document.getElementById('userEmailDisplay').textContent = email;

            // Load collection stats
            loadCollectionStats();
          } else {
            // Not logged in, redirect to login
            if (!window.location.pathname.includes('login.html') && !window.location.pathname.includes('register.html')) {
              window.location.href = 'login.html';
            }
          }
        });
      } catch (error) {
        console.error('Auth initialization error:', error);
      }
    })();
  }
}

async function loadCollectionStats() {
  try {
    const count = await firebaseDB.getCollectionCount();
    const cards = await firebaseDB.getCollectionCards();
    const uniqueCount = new Set(cards.map(c => c.name)).size;

    document.getElementById('totalCardsMenu').textContent = count + ' Cards';
    document.getElementById('uniqueCardsMenu').textContent = uniqueCount + ' Unique';
  } catch (error) {
    console.error('Error loading stats:', error);
  }
}

async function searchCollection(event) {
  event.preventDefault();
  const query = document.getElementById('collectionSearch').value;
  // Store in sessionStorage to pass to collection page
  sessionStorage.setItem('searchQuery', query);
  window.location.href = 'card_addition.html';
}

function toggleSubmenu(event) {
  const menu = event.target.nextElementSibling;
  if (menu) {
    menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
  }
}

async function logoutUser(event) {
  event.preventDefault();
  try {
    await firebaseDB.logout();
    window.location.href = 'login.html';
  } catch (error) {
    console.error('Logout error:', error);
  }
}

// Initialize navigation when DOM is ready
document.addEventListener('DOMContentLoaded', initializeNav);
