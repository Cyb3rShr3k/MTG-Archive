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
      const response = await fetch(
        'https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=' + this.apiKey,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            email: email,
            password: password,
            returnSecureToken: true
          })
        }
      );

      const data = await response.json();
      if (!response.ok) {
        const errorMsg = data.error?.message || JSON.stringify(data.error) || 'Registration failed';
        console.error('Registration error:', data);
        return { success: false, error: errorMsg };
      }

      // Store auth token and user info
      this.idToken = data.idToken;
      this.currentUser = {
        uid: data.localId,
        email: email,
        username: username
      };

      // Create user document
      await this.createDocument('users', data.localId, {
        username: username,
        email: email,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });

      return { success: true, userId: data.localId, message: 'Registration successful!' };
    } catch (error) {
      console.error('Register catch error:', error);
      return { success: false, error: error.message };
    }
  }

  async login(email, password) {
    try {
      const response = await fetch(
        'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=' + this.apiKey,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            email: email,
            password: password,
            returnSecureToken: true
          })
        }
      );

      const data = await response.json();
      if (!response.ok) {
        const errorMsg = data.error?.message || JSON.stringify(data.error) || 'Login failed';
        console.error('Login error:', data);
        return { success: false, error: errorMsg };
      }

      this.idToken = data.idToken;
      this.currentUser = {
        uid: data.localId,
        email: email
      };

      return { success: true, userId: data.localId, message: 'Login successful!' };
    } catch (error) {
      console.error('Login catch error:', error);
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

  // ============ DECK MANAGEMENT ============

  async createDeck(deckData) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      const deckId = `deck_${Date.now()}`;
      const path = `${this.baseUrl}/decks/${this.currentUser.uid}/decks/${deckId}`;

      const firebaseData = this.toFirestoreValue({
        name: deckData.name,
        deckType: deckData.deckType || 'Standard',
        commander: deckData.commander || null,
        cards: deckData.cards || [],
        colors: deckData.colors || '',
        description: deckData.description || '',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });

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
        return { success: false, error: error.error?.message || 'Create deck failed' };
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
      const path = `${this.baseUrl}/decks/${this.currentUser.uid}/decks`;

      const response = await fetch(path, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.idToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        return [];
      }

      const data = await response.json();
      if (!data.documents) return [];

      return data.documents.map(doc => ({
        id: doc.name.split('/').pop(),
        ...this.fromFirestoreValue(doc.fields)
      }));
    } catch (error) {
      console.error('Error getting decks:', error);
      return [];
    }
  }

  async updateDeck(deckId, deckData) {
    if (!this.currentUser) {
      return { success: false, error: 'User not authenticated' };
    }

    try {
      const path = `${this.baseUrl}/decks/${this.currentUser.uid}/decks/${deckId}`;

      deckData.updatedAt = new Date().toISOString();
      const firebaseData = this.toFirestoreValue(deckData);

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
        return { success: false, error: error.error?.message || 'Update deck failed' };
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
      const path = `${this.baseUrl}/decks/${this.currentUser.uid}/decks/${deckId}`;

      const response = await fetch(path, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.idToken}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        return { success: false, error: error.error?.message || 'Delete deck failed' };
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
}

// Initialize with Firebase config
const firebaseRest = new FirebaseRestAPI(
  'mtg-archive-357ca',
  'AIzaSyDmAJwEgZmtAslI7Ib_UqF6uqNfhcb5S6s'
);

// Compatibility wrapper to use as firebaseDB
const firebaseDB = firebaseRest;
