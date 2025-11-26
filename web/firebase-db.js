// Firebase Utility Library
// Handles all Firebase operations for collections, decks, and authentication

class FirebaseDB {
  constructor() {
    this.db = null;
    this.auth = null;
    this.currentUser = null;
    this.initialized = false;
  }

  async initialize() {
    if (this.initialized) return;
    
    // Wait for firebaseServices to be available
    for (let i = 0; i < 50; i++) {
      if (window.firebaseServices) {
        this.db = window.firebaseServices.db;
        this.auth = window.firebaseServices.auth;
        this.initialized = true;
        return;
      }
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    throw new Error('Firebase services not initialized');
  }

  // ============ AUTHENTICATION ============

  async register(email, username, password) {
    try {
      await this.initialize();
      const result = await this.auth.createUserWithEmailAndPassword(email, password);
      const userId = result.user.uid;

      // Create user document
      await this.db.collection('users').doc(userId).set({
        username: username,
        email: email,
        createdAt: new Date(),
        updatedAt: new Date()
      });

      return { success: true, userId, message: 'Registration successful!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async login(email, password) {
    try {
      await this.initialize();
      const result = await this.auth.signInWithEmailAndPassword(email, password);
      this.currentUser = result.user;
      return { success: true, userId: result.user.uid, message: 'Login successful!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async logout() {
    try {
      await this.initialize();
      await this.auth.signOut();
      this.currentUser = null;
      return { success: true, message: 'Logged out successfully!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  getCurrentUser() {
    return this.currentUser || this.auth.currentUser;
  }

  async getCurrentUserInfo() {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) return null;

    try {
      const doc = await this.db.collection('users').doc(user.uid).get();
      return doc.exists ? { userId: user.uid, ...doc.data() } : null;
    } catch (error) {
      console.error('Error getting user info:', error);
      return null;
    }
  }

  // ============ COLLECTION MANAGEMENT ============

  async addCard(cardData) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const cardId = `${cardData.scryfall_id}_${Date.now()}`;
      const collectionRef = this.db.collection('collections').doc(user.uid);
      
      await collectionRef.collection('cards').doc(cardId).set({
        ...cardData,
        addedAt: new Date(),
        quantity: cardData.quantity || 1
      });

      return { success: true, cardId, message: 'Card added!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getCollectionCards() {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const snapshot = await this.db
        .collection('collections')
        .doc(user.uid)
        .collection('cards')
        .get();

      return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    } catch (error) {
      console.error('Error getting collection:', error);
      return [];
    }
  }

  async getCollectionCount() {
    const cards = await this.getCollectionCards();
    return cards.reduce((sum, card) => sum + (card.quantity || 1), 0);
  }

  async searchCollection(query) {
    const cards = await this.getCollectionCards();
    const lowerQuery = query.toLowerCase();

    return cards.filter(card =>
      card.name.toLowerCase().includes(lowerQuery) ||
      (card.set && card.set.toLowerCase().includes(lowerQuery)) ||
      (card.type && card.type.toLowerCase().includes(lowerQuery))
    );
  }

  async updateCardQuantity(cardId, quantity) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      await this.db
        .collection('collections')
        .doc(user.uid)
        .collection('cards')
        .doc(cardId)
        .update({ quantity });

      return { success: true, message: 'Card updated!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async removeCard(cardId) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      await this.db
        .collection('collections')
        .doc(user.uid)
        .collection('cards')
        .doc(cardId)
        .delete();

      return { success: true, message: 'Card removed!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ============ DECK MANAGEMENT ============

  async createDeck(deckData) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const deckRef = this.db.collection('decks').doc(user.uid).collection('decks');
      const deckId = `deck_${Date.now()}`;

      await deckRef.doc(deckId).set({
        name: deckData.name,
        deckType: deckData.deckType || 'Standard',
        commander: deckData.commander || null,
        cards: deckData.cards || [],
        colors: deckData.colors || '',
        description: deckData.description || '',
        createdAt: new Date(),
        updatedAt: new Date()
      });

      return { success: true, deckId, message: 'Deck created!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getDecks() {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) return [];

    try {
      const snapshot = await this.db
        .collection('decks')
        .doc(user.uid)
        .collection('decks')
        .orderBy('updatedAt', 'desc')
        .get();

      return snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    } catch (error) {
      console.error('Error getting decks:', error);
      return [];
    }
  }

  async getDeck(deckId) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const doc = await this.db
        .collection('decks')
        .doc(user.uid)
        .collection('decks')
        .doc(deckId)
        .get();

      return doc.exists ? { id: doc.id, ...doc.data() } : null;
    } catch (error) {
      console.error('Error getting deck:', error);
      return null;
    }
  }

  async updateDeck(deckId, deckData) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      await this.db
        .collection('decks')
        .doc(user.uid)
        .collection('decks')
        .doc(deckId)
        .update({
          ...deckData,
          updatedAt: new Date()
        });

      return { success: true, message: 'Deck updated!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async deleteDeck(deckId) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      await this.db
        .collection('decks')
        .doc(user.uid)
        .collection('decks')
        .doc(deckId)
        .delete();

      return { success: true, message: 'Deck deleted!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async addCardToDeck(deckId, card) {
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const deck = await this.getDeck(deckId);
      if (!deck) throw new Error('Deck not found');

      const existingCard = deck.cards.find(c => c.id === card.id);
      if (existingCard) {
        existingCard.quantity = (existingCard.quantity || 1) + 1;
      } else {
        deck.cards.push({ ...card, quantity: 1 });
      }

      await this.updateDeck(deckId, { cards: deck.cards });
      return { success: true, message: 'Card added to deck!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async removeCardFromDeck(deckId, cardId) {
    const user = this.getCurrentUser();
    if (!user) throw new Error('User not authenticated');

    try {
      const deck = await this.getDeck(deckId);
      if (!deck) throw new Error('Deck not found');

      deck.cards = deck.cards.filter(c => c.id !== cardId);
      await this.updateDeck(deckId, { cards: deck.cards });
      return { success: true, message: 'Card removed from deck!' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  // ============ LISTENER SETUP ============

  async onAuthStateChanged(callback) {
    await this.initialize();
    return this.auth.onAuthStateChanged(user => {
      this.currentUser = user;
      callback(user);
    });
  }

  async onCollectionChanged(callback) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) return () => {};

    return this.db
      .collection('collections')
      .doc(user.uid)
      .collection('cards')
      .onSnapshot(
        snapshot => {
          const cards = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
          callback(cards);
        },
        error => console.error('Collection listener error:', error)
      );
  }

  async onDecksChanged(callback) {
    await this.initialize();
    const user = this.getCurrentUser();
    if (!user) return () => {};

    return this.db
      .collection('decks')
      .doc(user.uid)
      .collection('decks')
      .orderBy('updatedAt', 'desc')
      .onSnapshot(
        snapshot => {
          const decks = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
          callback(decks);
        },
        error => console.error('Decks listener error:', error)
      );
  }
}

// Create global instance
const firebaseDB = new FirebaseDB();
