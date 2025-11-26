/**
 * API wrapper for Flask backend
 * Replaces window.pywebview.api with fetch() calls
 */

const api = {
    /**
     * Call a backend API method
     * @param {string} methodName - The API method name
     * @param {object} params - Parameters to pass to the method
     * @returns {Promise<any>} - The API response
     */
    async call(methodName, params = {}) {
        const url = `/api/${methodName}`;
        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(params)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`API call failed: ${methodName}`, error);
            throw error;
        }
    }
};

// Create proxy object that mimics window.pywebview.api structure
window.pywebview = {
    api: new Proxy({}, {
        get: function(target, methodName) {
            return function(...args) {
                // Convert positional arguments to named parameters
                // Most methods expect keyword arguments
                const params = args[0] || {};
                return api.call(methodName, params);
            };
        }
    })
};
