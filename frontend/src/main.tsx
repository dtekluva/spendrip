import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import UpdateBar from './components/UpdateBar';
import { StoreProvider } from './lib/store';
import './styles.css';
import { captureSource } from './lib/analytics';
import './lib/install';  // listen for the browser's install offer from the very start

captureSource();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <StoreProvider>
        <App />
        <UpdateBar />
      </StoreProvider>
    </BrowserRouter>
  </StrictMode>,
);
