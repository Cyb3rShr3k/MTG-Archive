// Firebase REST API Handler
// Provides Firebase operations without requiring the JavaScript SDK
// Uses Firestore REST API directly via fetch()

class FirebaseRestAPI {
  constructor(projectId, apiKey) {
    this.projectId = projectId;
    this.apiKey = apiKey;
    this.baseUrl = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents`;
    this.currentUser = null;
    this.idToken = null;
  }

  // ============ AUTHENTICATION ============

  async register(email, password, username) {
    try {
      console.log('Registering user via backend:', email, username);
      
      // Call backend server instead of Google API
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email: email,
          password: password,
          username: username
        })
      });

      const data = await response.json();
      
      if (response.ok && data.success) {
        // Store auth token and user info
        this.idToken = data.token;
        this.currentUser = {
          uid: data.userId,
          email: data.email,
          username: data.username
        };

        // Save to localStorage for persistence
        try {
          localStorage.setItem('firebaseDB_token', data.token);
          localStorage.setItem('firebaseDB_user', JSON.stringify(this.currentUser));
        } catch (e) {
          console.warn('Could not save to localStorage:', e);
        }

        return { success: true, userId: data.userId, message: 'Registration successful!' };
      } else {
        const errorMsg = data.error || 'Registration failed';
        console.error('Registration failed:', data);
        return { success: false, error: errorMsg };
      }
    } catch (error) {
      console.error('Register error:', error);
      return { success: false, error: error.message };
    }
  }

  async login(email, password) {
    try {
      console.log('Logging in user via backend:', email);
      
      // Call backend server instead of Google API
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          email: email,
          password: password
        })
      });

      const data = await response.json();
      
      if (response.ok && data.success) {
        this.idToken = data.token;
        this.currentUser = {
          uid: data.userId,
          email: data.email,
          username: data.username
        };

        // Save to localStorage for persistence
        try {
          localStorage.setItem('firebaseDB_token', data.token);
          localStorage.setItem('firebaseDB_user', JSON.stringify(this.currentUser));
        } catch (e) {
          console.warn('Could not save to localStorage:', e);
        }

        return { success: true, userId: data.userId, message: 'Login successful!' };
      } else {
        const errorMsg = data.error || 'Login failed';
        console.error('Login failed:', data);
        return { success: false, error: errorMsg };
      }
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: error.message };
    }
  }

  async logout() {
    this.idToken = null;
    this.currentUser = null;
    return { success: true, message: 'Logged out successfully!' };
  }

  // ============ FIRESTORE OPERATIONS ============

  async createDocument(collection, docId, data) {
    if (!this.idToken || !this.currentUser) {
      throw new Error('User not authenticated');
    }

    const path = `${this.baseUrl}/${collection}/${docId}`;
    const firebaseData = this.toFirestoreValue(data);

    try {
      const response = await fetch(path, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${this.idToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          fields: firebaseData
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error?.message || 'Create document failed');
      }

      return { success: true, message: 'Document created' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getDocument(collection, docId) {
    if (!this.idToken) {
      throw new Error('User not authenticated');
    }

    const path = `${this.baseUrl}/${collection}/${docId}`;

    try {
      const response = await fetch(path, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.idToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return this.fromFirestoreValue(data.fields);
    } catch (error) {
      console.error('Error getting document:', error);
      return null;
    }
  }

  // ============ COLLECTION MANAGEMENT ============

  async addToCollection(cards) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      const collection = this.getStoredCollection();
      
      for (const card of cards) {
        const cardName = card.name || card;
        const quantity = card.quantity || 1;
        
        // Find existing card entry
        const existingIndex = collection.findIndex(c => c.name.toLowerCase() === cardName.toLowerCase());
        
        if (existingIndex >= 0) {
          collection[existingIndex].quantity = (collection[existingIndex].quantity || 1) + quantity;
        } else {
          collection.push({
            name: cardName,
            quantity: quantity,
            addedAt: new Date().toISOString()
          });
        }
        
        // Also add to backend user collection
        try {
          await fetch('/api/add_to_user_collection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              card_name: cardName,
              quantity: quantity
            })
          });
        } catch (e) {
          console.warn('Could not add to backend collection:', e);
        }
      }
      
      try {
        localStorage.setItem(`collection_${this.currentUser.uid}`, JSON.stringify(collection));
        console.log('✅ Cards added to collection (local + backend)');
      } catch (e) {
        console.warn('Could not save collection to localStorage:', e);
      }
      
      return { success: true, message: 'Cards added to collection' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  getStoredCollection() {
    if (!this.currentUser) return [];
    
    try {
      const stored = localStorage.getItem(`collection_${this.currentUser.uid}`);
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      console.warn('Could not read collection from localStorage:', e);
      return [];
    }
  }

  async getCollection() {
    return this.getStoredCollection();
  }

  async getCollectionCount() {
    const collection = this.getStoredCollection();
    return collection.reduce((sum, card) => sum + (card.quantity || 1), 0);
  }

  // ============ DECK MANAGEMENT ============

  async createDeck(deckData) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      const deckId = `deck_${Date.now()}`;
      
      // Store deck in localStorage (simpler than Firestore REST API auth issues)
      const decks = this.getStoredDecks();
      
      const newDeck = {
        id: deckId,
        name: deckData.name,
        deckType: deckData.deckType || 'Commander',
        commander: deckData.commander || null,
        cards: deckData.cards || [],
        colors: deckData.colors || '',
        description: deckData.description || '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      
      decks.push(newDeck);
      
      try {
        localStorage.setItem(`decks_${this.currentUser.uid}`, JSON.stringify(decks));
        console.log('✅ Deck saved to localStorage:', deckId);
      } catch (e) {
        console.warn('Could not save to localStorage:', e);
      }
      
      // Also save to backend user collection database
      try {
        const deckDataForBackend = {
          deck_name: deckData.name,
          items: deckData.cards || [],
          deck_type: deckData.deckType || 'Commander',
          commander: deckData.commander || null
        };
        
        const response = await fetch('/api/save_user_deck', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(deckDataForBackend)
        });
        
        if (response.ok) {
          console.log('✅ Deck also saved to backend database');
        }
      } catch (e) {
        console.warn('Could not save to backend:', e);
      }
      
      // Also add cards to collection
      if (deckData.cards && deckData.cards.length > 0) {
        await this.addToCollection(deckData.cards);
      }
      
      return { success: true, deckId, message: 'Deck created!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getDecks() {
    if (!this.currentUser) {
      return [];
    }

    try {
      return this.getStoredDecks();
    } catch (error) {
      console.error('Error getting decks:', error);
      return [];
    }
  }

  getStoredDecks() {
    if (!this.currentUser) return [];
    
    try {
      const stored = localStorage.getItem(`decks_${this.currentUser.uid}`);
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      console.warn('Could not read decks from localStorage:', e);
      return [];
    }
  }

  async updateDeck(deckId, deckData) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      const decks = this.getStoredDecks();
      const deckIndex = decks.findIndex(d => d.id === deckId);
      
      if (deckIndex === -1) {
        return { success: false, error: 'Deck not found' };
      }

      decks[deckIndex] = {
        ...decks[deckIndex],
        ...deckData,
        updatedAt: new Date().toISOString()
      };

      try {
        localStorage.setItem(`decks_${this.currentUser.uid}`, JSON.stringify(decks));
        console.log('✅ Deck updated in localStorage:', deckId);
      } catch (e) {
        console.warn('Could not save to localStorage:', e);
      }

      return { success: true, message: 'Deck updated!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async deleteDeck(deckId) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      let decks = this.getStoredDecks();
      decks = decks.filter(d => d.id !== deckId);

      try {
        localStorage.setItem(`decks_${this.currentUser.uid}`, JSON.stringify(decks));
        console.log('✅ Deck deleted from localStorage:', deckId);
      } catch (e) {
        console.warn('Could not save to localStorage:', e);
      }

      return { success: true, message: 'Deck deleted!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ============ UTILITY FUNCTIONS ============

  toFirestoreValue(value) {
    if (value === null || value === undefined) {
      return { nullValue: null };
    }

    if (typeof value === 'boolean') {
      return { booleanValue: value };
    }

    if (typeof value === 'number') {
      if (Number.isInteger(value)) {
        return { integerValue: value.toString() };
      }
      return { doubleValue: value };
    }

    if (typeof value === 'string') {
      return { stringValue: value };
    }

    if (Array.isArray(value)) {
      return {
        arrayValue: {
          values: value.map(v => this.toFirestoreValue(v))
        }
      };
    }

    if (typeof value === 'object') {
      const mapValue = {};
      for (const [key, val] of Object.entries(value)) {
        mapValue[key] = this.toFirestoreValue(val);
      }
      return { mapValue: { fields: mapValue } };
    }

    return { stringValue: String(value) };
  }

  fromFirestoreValue(fields) {
    if (!fields) return {};

    const result = {};
    for (const [key, field] of Object.entries(fields)) {
      result[key] = this.extractValue(field);
    }
    return result;
  }

  extractValue(field) {
    if (field.nullValue !== undefined) return null;
    if (field.booleanValue !== undefined) return field.booleanValue;
    if (field.integerValue !== undefined) return parseInt(field.integerValue);
    if (field.doubleValue !== undefined) return field.doubleValue;
    if (field.stringValue !== undefined) return field.stringValue;
    if (field.arrayValue) {
      return field.arrayValue.values?.map(v => this.extractValue(v)) || [];
    }
    if (field.mapValue) {
      return this.fromFirestoreValue(field.mapValue.fields);
    }
    return null;
  }

  getCurrentUser() {
    return this.currentUser;
  }

  // Get current user info (alias for getCurrentUser for compatibility)
  async getCurrentUserInfo() {
    return this.currentUser;
  }

  // Restore user session from localStorage
  restoreSession() {
    try {
      const token = localStorage.getItem('firebaseDB_token');
      const userStr = localStorage.getItem('firebaseDB_user');
      
      if (token && userStr) {
        this.idToken = token;
        this.currentUser = JSON.parse(userStr);
        console.log('✅ Session restored from localStorage:', this.currentUser.email);
        return true;
      }
    } catch (e) {
      console.warn('Could not restore session from localStorage:', e);
    }
    return false;
  }
}

// Initialize with Firebase config
const firebaseRest = new FirebaseRestAPI(
  'mtg-archive-357ca',
  'AIzaSyDmAJwEgZmtAslI7Ib_UqF6uqNfhcb5S6s'
);

// Restore session from localStorage on load
firebaseRest.restoreSession();

// Compatibility wrapper to use as firebaseDB
const firebaseDB = firebaseRest;
