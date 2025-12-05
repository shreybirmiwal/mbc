const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  console.log('[setupProxy] Configuring proxy middleware...');
  
  const proxyMiddleware = createProxyMiddleware({
    target: 'http://127.0.0.1:5000',
    changeOrigin: true,
    secure: false,
    logLevel: 'debug',
    onProxyReq: (proxyReq, req, res) => {
      console.log(`[PROXY] ${req.method} ${req.url} -> http://127.0.0.1:5000${req.url}`);
    },
    onError: (err, req, res) => {
      console.error('[PROXY ERROR]', err);
    }
  });
  
  app.use('/admin', proxyMiddleware);
  console.log('[setupProxy] Proxy configured for /admin routes');
};
