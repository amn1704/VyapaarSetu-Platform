import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import LandingPage from './pages/LandingPage';
import Dashboard from './pages/Dashboard';
import BusinessDirectory from './pages/BusinessDirectory';
import ReviewQueue from './pages/ReviewQueue';
import RawRecords from './pages/RawRecords';
import EntityLinker from './pages/EntityLinker';
import ActivityStatus from './pages/ActivityStatus';
import QueryEngine from './pages/QueryEngine';
import { useI18n } from './i18n';

function App() {
  const { lang, toggleLang } = useI18n();

  return (
    <Router>
      <Layout lang={lang} toggleLang={toggleLang}>
        <Routes>
          <Route path="/" element={<LandingPage lang={lang} />} />
          <Route path="/dashboard" element={<Dashboard lang={lang} />} />
          <Route path="/business-directory" element={<BusinessDirectory lang={lang} />} />
          <Route path="/raw-records" element={<RawRecords lang={lang} />} />
          <Route path="/entity-linker" element={<EntityLinker lang={lang} />} />
          <Route path="/review" element={<ReviewQueue lang={lang} />} />
          <Route path="/activity-status" element={<ActivityStatus lang={lang} />} />
          <Route path="/query-engine" element={<QueryEngine lang={lang} />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
