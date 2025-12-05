const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  // Proxy all /admin API routes to the backend
  app.use(
    '/admin',
    createProxyMiddleware({
      target: 'http://127.0.0.1:5000',
      changeOrigin: true,
      ws: true, // Enable websocket proxying
    })
  );
};
