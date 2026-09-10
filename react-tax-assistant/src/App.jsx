import React, { useState, useEffect } from 'react';
import './index.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? (
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://127.0.0.1:8000'
    : ''
);

const STORAGE_KEY = 'tax_compass_user_data';

const getStoredData = () => {
  try {
    // Clean up any legacy localStorage entry
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {}

    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (err) {
    console.error('Error loading saved state from sessionStorage:', err);
  }
  return null;
};

export default function App() {
  const storedData = React.useMemo(() => getStoredData() || {}, []);

  // State management
  const [servicesList, setServicesList] = useState([]);
  const [selectedService, setSelectedService] = useState(() => storedData.selectedService || '');
  const [serviceDetails, setServiceDetails] = useState(() => storedData.serviceDetails || null);

  const [docInput, setDocInput] = useState(() => storedData.docInput || '');
  const [documents, setDocuments] = useState(() => storedData.documents || []);
  const [situationNote, setSituationNote] = useState(() => storedData.situationNote || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [assistancePlan, setAssistancePlan] = useState(() => storedData.assistancePlan || null);

  const [apiStatus, setApiStatus] = useState('loading'); // 'loading' | 'connected' | 'error'
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [openGuides, setOpenGuides] = useState(() => storedData.openGuides || {});

  // Chat / situation state
  const [chatSessionId, setChatSessionId] = useState(() => storedData.chatSessionId || null);
  const [chatMessages, setChatMessages] = useState(() => storedData.chatMessages || []); // {role:'user'|'bot', text:string}
  const [chatInput, setChatInput] = useState(() => storedData.chatInput || '');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatComplete, setChatComplete] = useState(() => storedData.chatComplete || false);
  const [userProfile, setUserProfile] = useState(() => storedData.userProfile || null);
  const [taxReport, setTaxReport] = useState(() => storedData.taxReport || null);
  const [taxReportLoading, setTaxReportLoading] = useState(false);

  // Ask-about-report mini-chat state
  const [askMessages, setAskMessages] = useState(() => storedData.askMessages || []);   // {role:'user'|'bot', text:string}
  const [askInput, setAskInput] = useState(() => storedData.askInput || '');
  const [askLoading, setAskLoading] = useState(false);
  const askBottomRef = React.useRef(null);
  const chatBottomRef = React.useRef(null);

  // Results tab state — default to 'tax-report'
  const [activeTab, setActiveTab] = useState(() => storedData.activeTab || 'tax-report');

  // Quick document suggestions (includes dynamic profile requirements)
  const suggestedDocs = React.useMemo(() => {
    const reqs = serviceDetails?.documents_required || [];
    const defaults = [
      'Form 16',
      'Form 26AS',
      'AIS',
      'Bank Statements',
      'Housing Loan Interest Certificate',
      'Rent Receipts',
      'Investment / Premium Payment Receipts',
      'Capital Gains Statement',
      'PAN Card',
      'Aadhaar Card',
    ];
    return Array.from(new Set([...reqs, ...defaults]));
  }, [serviceDetails]);

  // Helper function to render text with clickable links
  const renderTextWithLinks = (text) => {
    if (!text) return null;
    const urlRegex = /(https?:\/\/[^\s\)]+)/g;
    const parts = text.split(urlRegex);

    return parts.map((part, index) => {
      if (part.match(/^https?:\/\//)) {
        const cleanUrl = part.replace(/[\.,\)]+$/, '');
        const trailingPunct = part.slice(cleanUrl.length);
        return (
          <React.Fragment key={index}>
            <a
              href={cleanUrl}
              target="_blank"
              rel="noreferrer"
              style={{ color: '#1d4ed8', textDecoration: 'underline', fontWeight: 600 }}
            >
              {cleanUrl}
            </a>
            {trailingPunct}
          </React.Fragment>
        );
      }
      return part;
    });
  };

  // Render markdown-lite: **bold**, *italic*, newlines → React elements
  const renderMarkdown = (text) => {
    if (!text) return null;
    // Split on **bold** and *italic* tokens, preserving delimiters
    const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em key={i}>{part.slice(1, -1)}</em>;
      }
      // Preserve line breaks
      return part.split('\n').map((line, j, arr) => (
        <React.Fragment key={`${i}-${j}`}>
          {line}
          {j < arr.length - 1 && <br />}
        </React.Fragment>
      ));
    });
  };
  const parseStepItem = (stepText, idx) => {
    if (!stepText) return { isAcquisition: false, text: '', stepNumber: idx + 1 };

    const match = stepText.match(/^(?:\d+\.\s*)?How to acquire ([^:]+):\s*(.*?)(?:\s*\(Source:\s*(.*?)\))?$/i);

    if (match) {
      const docName = match[1].trim();
      const rawSteps = match[2].trim();
      const sourceInfo = match[3] ? match[3].trim() : null;

      let subSteps = [];
      if (rawSteps.includes(' -> ')) {
        subSteps = rawSteps.split(' -> ').map((s) => s.trim()).filter(Boolean);
      } else {
        subSteps = rawSteps.split(/(?<=\.)\s+/).map((s) => s.trim()).filter(Boolean);
      }
      if (subSteps.length === 0) subSteps = [rawSteps];

      return {
        isAcquisition: true,
        docName,
        title: `How to acquire ${docName}`,
        source: sourceInfo,
        subSteps,
        stepNumber: idx + 1,
      };
    }

    const cleanedText = stepText.replace(/^\d+\.\s*/, '');

    return {
      isAcquisition: false,
      text: cleanedText,
      stepNumber: idx + 1,
    };
  };

  const toggleGuide = (idx) => {
    setOpenGuides((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  // 1. Fetch available services list from FastAPI backend on mount
  const fetchServices = () => {
    setApiStatus('loading');
    fetch(`${API_BASE_URL}/services`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setServicesList(data);
        setApiStatus('connected');
      })
      .catch((err) => {
        console.error('Failed to fetch services from FastAPI:', err);
        setApiStatus('error');
      });
  };

  useEffect(() => {
    fetchServices();
  }, []);

  // 2. Fetch specific service details from FastAPI backend when selectedService changes
  useEffect(() => {
    if (!selectedService) {
      setServiceDetails(null);
      return;
    }

    setIsLoadingDetails(true);
    const sessionQuery = chatSessionId ? `?session_id=${encodeURIComponent(chatSessionId)}` : '';
    fetch(`${API_BASE_URL}/services/${selectedService}${sessionQuery}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setServiceDetails(data);
        setIsLoadingDetails(false);
      })
      .catch((err) => {
        console.error(`Failed to fetch service details for ${selectedService}:`, err);
        setIsLoadingDetails(false);
      });
  }, [selectedService, chatSessionId, userProfile]);

  // Add document handler
  const handleAddDocument = (docName) => {
    const trimmed = docName.trim();
    if (trimmed && !documents.some((d) => d.toLowerCase() === trimmed.toLowerCase())) {
      setDocuments([...documents, trimmed]);
      setDocInput('');
      setAssistancePlan(null);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddDocument(docInput);
    }
  };

  // Remove document handler
  const handleRemoveDocument = (docToRemove) => {
    setDocuments(documents.filter((doc) => doc !== docToRemove));
    setAssistancePlan(null);
  };

  // Generate assistance plan
  const handleGenerateGuidance = () => {
    if (!selectedService || !serviceDetails) return;
    setIsSubmitting(true);
    const sessionQuery = chatSessionId ? `?session_id=${encodeURIComponent(chatSessionId)}` : '';
    fetch(`${API_BASE_URL}/services/${selectedService}/roadmap${sessionQuery}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_documents: documents,
        added_documents: documents,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setIsSubmitting(false);
        setAssistancePlan({
          generatedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          service: selectedService,
          roadmap: data,
        });
      })
      .catch((err) => {
        console.error('Failed to generate guidance from backend:', err);
        setIsSubmitting(false);
      });
  };

  // Helper check if user document satisfies requirement
  const isDocPresent = (reqName) => {
    return documents.some((userDoc) =>
      userDoc.toLowerCase().includes(reqName.toLowerCase()) ||
      reqName.toLowerCase().includes(userDoc.toLowerCase())
    );
  };

  // Auto-scroll chat window whenever a new message arrives within the chat container
  const chatContainerRef = React.useRef(null);
  useEffect(() => {
    // Scroll the container to its bottom without affecting the whole page
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({ top: chatContainerRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [chatMessages, chatLoading]);


  const fetchTaxReport = async (sid) => {
    setTaxReportLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/tax-report/${sid}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTaxReport(data.tax_report);
    } catch (err) {
      setTaxReport({ error: 'Could not generate tax report. Please try again.' });
    } finally {
      setTaxReportLoading(false);
    }
  };

  // Send a message to POST /chat/message and handle the response
  const sendChatMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || chatLoading || chatComplete) return;

    // Optimistically show the user's message
    setChatMessages((prev) => [...prev, { role: 'user', text: trimmed }]);
    setChatInput('');
    setChatLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: chatSessionId || undefined,
          message: trimmed,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      // Persist session id from first response onwards
      if (!chatSessionId) setChatSessionId(data.session_id);

      // Append bot reply
      setChatMessages((prev) => [...prev, { role: 'bot', text: data.reply }]);

      if (data.is_complete && data.profile) {
        setChatComplete(true);
        setUserProfile(data.profile);
        // Auto-fetch tax report as soon as profile is complete
        fetchTaxReport(data.session_id);
      }
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        { role: 'bot', text: 'Sorry, something went wrong. Please check the backend and try again.' },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleChatKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(chatInput);
    }
  };

  // Sync state to sessionStorage whenever user data updates
  useEffect(() => {
    const hasData =
      Boolean(chatSessionId) ||
      chatMessages.length > 0 ||
      Boolean(situationNote.trim()) ||
      documents.length > 0 ||
      Boolean(selectedService) ||
      Boolean(assistancePlan) ||
      Boolean(userProfile) ||
      Boolean(taxReport) ||
      askMessages.length > 0;

    if (hasData) {
      try {
        sessionStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            selectedService,
            serviceDetails,
            docInput,
            documents,
            situationNote,
            assistancePlan,
            openGuides,
            chatSessionId,
            chatMessages,
            chatInput,
            chatComplete,
            userProfile,
            taxReport,
            askMessages,
            askInput,
            activeTab,
          })
        );
      } catch (err) {
        console.error('Error saving state to sessionStorage:', err);
      }
    } else {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch (err) {
        console.error('Error removing state from sessionStorage:', err);
      }
    }
  }, [
    selectedService,
    serviceDetails,
    docInput,
    documents,
    situationNote,
    assistancePlan,
    openGuides,
    chatSessionId,
    chatMessages,
    chatInput,
    chatComplete,
    userProfile,
    taxReport,
    askMessages,
    askInput,
    activeTab,
  ]);

  // Fallback: if chat was completed and session exists but tax report is missing, fetch it
  useEffect(() => {
    if (chatComplete && chatSessionId && !taxReport && !taxReportLoading) {
      fetchTaxReport(chatSessionId);
    }
  }, [chatComplete, chatSessionId, taxReport, taxReportLoading]);

  const resetChat = () => {
    if (chatSessionId) {
      fetch(`${API_BASE_URL}/chat/session/${chatSessionId}`, { method: 'DELETE' }).catch(() => {});
    }
    try {
      sessionStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(STORAGE_KEY);
    } catch (err) {
      console.error('Error removing state from sessionStorage:', err);
    }
    setChatSessionId(null);
    setChatMessages([]);
    setChatInput('');
    setChatLoading(false);
    setChatComplete(false);
    setUserProfile(null);
    setTaxReport(null);
    setTaxReportLoading(false);
    setAskMessages([]);
    setAskInput('');
    setAskLoading(false);
    setSituationNote('');
    setSelectedService('');
    setServiceDetails(null);
    setDocInput('');
    setDocuments([]);
    setAssistancePlan(null);
    setOpenGuides({});
    setActiveTab('tax-report');
  };

  // Auto-scroll ask-report chat
  const askContainerRef = React.useRef(null);
  useEffect(() => {
    if (askContainerRef.current) {
      askContainerRef.current.scrollTo({ top: askContainerRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [askMessages, askLoading]);


  const sendAskMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed || askLoading || !chatSessionId) return;

    setAskMessages((prev) => [...prev, { role: 'user', text: trimmed }]);
    setAskInput('');
    setAskLoading(true);

    // Build history in the format the backend expects
    const history = askMessages.map((m) => ({
      role: m.role === 'bot' ? 'assistant' : 'user',
      content: m.text,
    }));

    try {
      const res = await fetch(`${API_BASE_URL}/ask-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: chatSessionId,
          question: trimmed,
          history,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAskMessages((prev) => [...prev, { role: 'bot', text: data.answer }]);
    } catch {
      setAskMessages((prev) => [
        ...prev,
        { role: 'bot', text: 'Sorry, something went wrong. Please try again.' },
      ]);
    } finally {
      setAskLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Top Navbar Header */}
      <header className="top-navbar">
        <div className="brand-logo">
          <div className="brand-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-name">Tax Compass</span>
            <span className="brand-tagline">Get answers grounded in official tax documents</span>
          </div>
        </div>
      </header>

      {/* Situation Section — full-width, highlighted, above the grid */}
      <section className="situation-section">
        <div className="situation-inner">

          {/* Header row */}
          <div className="situation-label-row">
            <div className="situation-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <div>
              <h2 className="situation-title">Describe Your Situation</h2>
              <p className="situation-subtitle">
                {chatComplete
                  ? 'Profile complete — your personalised guidance is ready.'
                  : chatMessages.length > 0
                    ? 'Answer the follow-up questions so the AI can tailor your guidance.'
                    : 'Start here — tell the AI about yourself and it will ask what it needs.'}
              </p>
            </div>
            {chatComplete && (
              <span className="situation-filled-badge">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
                Profile collected
              </span>
            )}
            {chatMessages.length > 0 && (
              <button type="button" className="situation-reset-btn" onClick={resetChat} title="Start over">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                  <path d="M3 3v5h5" />
                </svg>
                Start over
              </button>
            )}
          </div>

          {/* ── Initial textarea + Submit (shown before chat starts) ── */}
          {chatMessages.length === 0 && (
            <>
              <div style={{ position: 'relative' }}>
                <textarea
                  id="situation-input"
                  className="situation-textarea"
                  rows={3}
                  placeholder="e.g. I am a salaried employee earning 12 LPA, filing ITR for the first time. I have Form 16 but I'm unsure about HRA and savings account interest..."
                  value={situationNote}
                  onChange={(e) => setSituationNote(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendChatMessage(situationNote);
                    }
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#60a5fa';
                    e.target.style.boxShadow = '0 0 0 4px rgba(96, 165, 250, 0.2)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(96, 165, 250, 0.45)';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
                <button
                  type="button"
                  className="situation-submit-btn"
                  disabled={!situationNote.trim() || chatLoading}
                  onClick={() => sendChatMessage(situationNote)}
                >
                  {chatLoading ? (
                    <>
                      <span className="situation-spinner" />
                      Thinking...
                    </>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13" />
                        <polygon points="22 2 15 22 11 13 2 9 22 2" />
                      </svg>
                      Submit &amp; Get Guidance
                    </>
                  )}
                </button>
              </div>
              <p className="situation-hint">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 16v-4" /><path d="M12 8h.01" />
                </svg>
                Press Enter or click Submit. The AI will ask follow-up questions to build your profile.
              </p>
            </>
          )}

          {/* ── Chat thread (shown once conversation starts) ── */}
          {chatMessages.length > 0 && (
            <div ref={chatContainerRef} className="chat-thread">
              {chatMessages.map((msg, i) => (
                <div key={i} className={`chat-bubble-row ${msg.role === 'user' ? 'chat-row-user' : 'chat-row-bot'}`}>
                  {msg.role === 'bot' && (
                    <div className="chat-avatar-bot">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                        <path d="M9 12l2 2 4-4" />
                      </svg>
                    </div>
                  )}
                  <div className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-bot'}`}>
                    {msg.role === 'bot' ? renderMarkdown(msg.text) : msg.text}
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {chatLoading && (
                <div className="chat-bubble-row chat-row-bot">
                  <div className="chat-avatar-bot">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                  </div>
                  <div className="chat-bubble chat-bubble-bot chat-typing">
                    <span /><span /><span />
                  </div>
                </div>
              )}
              <div ref={chatBottomRef} />
            </div>
          )}

          {/* ── Follow-up input (shown while chat is active and not complete) ── */}
          {chatMessages.length > 0 && !chatComplete && (
            <div className="chat-input-row">
              <input
                type="text"
                className="chat-followup-input"
                placeholder="Type your answer..."
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleChatKeyDown}
                disabled={chatLoading}
                autoFocus
              />
              <button
                type="button"
                className="chat-send-btn"
                disabled={!chatInput.trim() || chatLoading}
                onClick={() => sendChatMessage(chatInput)}
              >
                {chatLoading ? <span className="situation-spinner" /> : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                )}
              </button>
            </div>
          )}

        </div>
      </section>

      {/* ── Results Tabs (shown once chat is complete) ─────────────── */}
      {(taxReportLoading || taxReport || chatComplete) && (
        <section className="results-tabs-section">

          {/* Tab Bar */}
          <div className="results-tab-bar">
            {[
              { id: 'tax-report', label: 'Tax Report', icon: (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
              )},
              { id: 'ask-report', label: 'Ask About Report', icon: (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
              )},
              { id: 'user-profile', label: 'User Profile', icon: (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              )},
              { id: 'next-steps', label: 'Next Steps', icon: (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              )},
              { id: 'service-guidance', label: 'Service Guidance', icon: (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>
              )},
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`results-tab-btn ${activeTab === tab.id ? 'results-tab-active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="results-tab-content">

            {/* ── TAX REPORT TAB ── */}
            {activeTab === 'tax-report' && (
              <>
                {taxReportLoading && (
                  <div className="tax-report-loading">
                    <span className="situation-spinner" style={{ width: 20, height: 20, borderWidth: 3 }} />
                    <span>Calculating your tax liability...</span>
                  </div>
                )}
                {!taxReportLoading && taxReport?.error && (
                  <div className="tax-report-error">{taxReport.error}</div>
                )}
                {!taxReportLoading && !taxReport && !taxReportLoading && (
                  <div className="tab-empty-state">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#93b9e8" strokeWidth="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <p>Complete the conversation to generate your tax report.</p>
                  </div>
                )}
              </>
            )}

            {/* ── NEXT STEPS TAB ── */}
            {activeTab === 'next-steps' && !taxReport && (
              <div className="tab-empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#93b9e8" strokeWidth="1.5"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                <p>Next steps will appear once your tax report is ready.</p>
              </div>
            )}

            {/* ── USER PROFILE TAB ── */}
            {activeTab === 'user-profile' && !userProfile && (
              <div className="tab-empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#93b9e8" strokeWidth="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                <p>Complete the conversation to see your extracted profile.</p>
              </div>
            )}
            {activeTab === 'user-profile' && chatComplete && userProfile && (
              <div className="profile-panel">
                <div className="profile-panel-header">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  Extracted User Profile
                </div>
                <div className="profile-grid">
                  <div className="profile-group">
                    <div className="profile-group-title">Employment</div>
                    {Object.entries(userProfile.employment || {}).map(([k, v]) =>
                      v != null && (
                        <div key={k} className="profile-row">
                          <span className="profile-key">{k.replace(/_/g, ' ')}</span>
                          <span className="profile-val">{String(v)}</span>
                        </div>
                      )
                    )}
                  </div>
                  <div className="profile-group">
                    <div className="profile-group-title">Additional Income</div>
                    {Object.entries(userProfile.additional_income || {}).map(([k, v]) =>
                      v != null && (
                        <div key={k} className="profile-row">
                          <span className="profile-key">{k.replace(/_/g, ' ')}</span>
                          <span className="profile-val">{String(v)}</span>
                        </div>
                      )
                    )}
                  </div>
                  <div className="profile-group">
                    <div className="profile-group-title">Deductions</div>
                    {Object.entries(userProfile.deductions || {}).map(([k, v]) =>
                      v != null && (
                        <div key={k} className="profile-row">
                          <span className="profile-key">{k.replace(/_/g, ' ')}</span>
                          <span className="profile-val">{String(v)}</span>
                        </div>
                      )
                    )}
                  </div>
                  <div className="profile-group">
                    <div className="profile-group-title">Filing</div>
                    {Object.entries(userProfile.filing || {}).map(([k, v]) =>
                      v != null && (
                        <div key={k} className="profile-row">
                          <span className="profile-key">{k.replace(/_/g, ' ')}</span>
                          <span className="profile-val">{String(v)}</span>
                        </div>
                      )
                    )}
                  </div>
                </div>
                {userProfile.situation_summary && (
                  <div className="profile-summary">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
                    </svg>
                    {userProfile.situation_summary}
                  </div>
                )}
              </div>
            )}

            {/* ── ASK ABOUT REPORT TAB ── */}
            {activeTab === 'ask-report' && !taxReport && (
              <div className="tab-empty-state">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#93b9e8" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
                <p>Generate your tax report first to ask questions about it.</p>
              </div>
            )}
            {activeTab === 'ask-report' && taxReport && !taxReport.error && (
              <div className="ask-report-section">
                <div className="ask-report-header">
                  <div className="ask-report-icon">
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>
                    </svg>
                  </div>
                  <div>
                    <h2 className="ask-report-title">Ask About the Report</h2>
                    <p className="ask-report-subtitle">Ask anything about your tax figures, deductions, or next steps — the AI has your full report as context.</p>
                  </div>
                </div>
                {askMessages.length === 0 && (
                  <div className="ask-suggestions">
                    {[
                      'Why is my old regime tax lower?',
                      'What documents do I need for 80C?',
                      'How much can I save by adding NPS?',
                      'Explain my taxable income calculation.',
                    ].map((q) => (
                      <button key={q} type="button" className="ask-suggestion-pill" onClick={() => sendAskMessage(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                )}
                {askMessages.length > 0 && (
                  <div ref={askContainerRef} className="ask-thread">
                    {askMessages.map((msg, i) => (
                      <div key={i} className={`ask-bubble-row ${msg.role === 'user' ? 'ask-row-user' : 'ask-row-bot'}`}>
                        {msg.role === 'bot' && (
                          <div className="ask-avatar">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                              <circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>
                            </svg>
                          </div>
                        )}
                        <div className={`ask-bubble ${msg.role === 'user' ? 'ask-bubble-user' : 'ask-bubble-bot'}`}>
                          {msg.role === 'bot' ? renderMarkdown(msg.text) : msg.text}
                        </div>
                      </div>
                    ))}
                    {askLoading && (
                      <div className="ask-bubble-row ask-row-bot">
                        <div className="ask-avatar">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                            <circle cx="12" cy="12" r="10"/>
                          </svg>
                        </div>
                        <div className="ask-bubble ask-bubble-bot chat-typing"><span /><span /><span /></div>
                      </div>
                    )}
                  </div>
                )}
                <div className="ask-input-row">
                  <input
                    type="text"
                    className="ask-input"
                    placeholder="e.g. Why is my taxable income lower in Old Regime?"
                    value={askInput}
                    onChange={(e) => setAskInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAskMessage(askInput); } }}
                    disabled={askLoading}
                  />
                  <button type="button" className="ask-send-btn" disabled={!askInput.trim() || askLoading} onClick={() => sendAskMessage(askInput)}>
                    {askLoading ? <span className="situation-spinner" /> : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* ── TAX REPORT + NEXT STEPS shared data (rendered inside correct tabs) ── */}
            {!taxReportLoading && taxReport && !taxReport.error && (() => {
              const rec    = taxReport.recommendation;
              const oldR   = taxReport.old_regime;
              const newR   = taxReport.new_regime;
              const winner = rec.choose;

              const fmt = (n) => `₹${Number(n).toLocaleString('en-IN')}`;

              const nextSteps = [
                winner === 'old'
                  ? `Declare Old Tax Regime on your ITR (opt out of New Regime).`
                  : winner === 'new'
                    ? `Declare New Tax Regime on your ITR (default from FY 2024-25).`
                    : `Either regime works equally — the New Regime requires no investment proofs.`,
                `Gather investment proof documents for 80C, 80D, and NPS before filing.`,
                `Download your Form 26AS / AIS from the Income Tax portal to verify TDS credit.`,
                `Log in at https://www.incometax.gov.in and pre-fill your ITR. Verify salary and TDS figures against Form 16.`,
                `Submit and e-Verify your ITR within 30 days using Aadhaar OTP or Net Banking EVC.`,
              ];

            return (
              <>
              {activeTab === 'tax-report' && (
              <div className="tax-report-grid">

                {/* ── LEFT: Regime comparison bars ── */}
                <div className="tax-report-card">
                  <div className="tr-card-header">
                    <div className="tr-card-icon">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                      </svg>
                    </div>
                    <div>
                      <h2 className="tr-card-title">Tax Liability Summary</h2>
                      <p className="tr-card-subtitle">{(() => { const now = new Date(); const fy = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1; return `FY ${fy}-${String(fy + 1).slice(-2)}`; })()} · Gross Income {fmt(taxReport.gross_total_income)}</p>
                    </div>
                  </div>

                  {/* Regime comparison bars */}
                  <div className="tr-regime-compare">
                    {[
                      { key: 'old', label: 'Old Regime', regime: oldR },
                      { key: 'new', label: 'New Regime', regime: newR },
                    ].map(({ key, label, regime }) => {
                      const maxTax = Math.max(oldR.total_tax, newR.total_tax) || 1;
                      const pct    = Math.round((regime.total_tax / maxTax) * 100);
                      return (
                        <div key={key} className={`tr-regime-row ${winner === key ? 'tr-regime-winner' : ''}`}>
                          <div className="tr-regime-top">
                            <span className="tr-regime-label">
                              {label}
                              {winner === key && (
                                <span className="tr-winner-badge">
                                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                                    <path d="M20 6L9 17l-5-5"/>
                                  </svg>
                                  Recommended
                                </span>
                              )}
                              {winner === 'tie' && key === 'old' && (
                                <span className="tr-tie-badge">Tie</span>
                              )}
                            </span>
                            <span className="tr-regime-tax">{fmt(regime.total_tax)}</span>
                          </div>
                          <div className="tr-bar-track">
                            <div
                              className={`tr-bar-fill ${winner === key ? 'tr-bar-winner' : 'tr-bar-other'}`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <div className="tr-deduction-row">
                            <span className="tr-ded-label">Deductions</span>
                            <span className="tr-ded-val">{fmt(regime.deductions.total)}</span>
                          </div>
                          <div className="tr-deduction-row">
                            <span className="tr-ded-label">Taxable income</span>
                            <span className="tr-ded-val">{fmt(regime.taxable_income)}</span>
                          </div>
                          {regime.rebate_87a > 0 && (
                            <div className="tr-deduction-row tr-rebate">
                              <span className="tr-ded-label">87A Rebate applied</span>
                              <span className="tr-ded-val">−{fmt(regime.rebate_87a)}</span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {/* Savings callout */}
                  {rec.savings > 0 && winner !== 'tie' && (
                    <div className={`tr-savings-callout ${winner === 'old' ? 'tr-savings-old' : 'tr-savings-new'}`}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 8v4l3 3"/>
                      </svg>
                      <div>
                        <strong>Save {fmt(rec.savings)}</strong> by choosing the{' '}
                        <strong>{winner === 'old' ? 'Old' : 'New'} Regime</strong>
                      </div>
                    </div>
                  )}

                  {/* ITR Form Applicable */}
                  {(() => {
                    const p = userProfile || {};
                    const emp = p.employment || {};
                    const inc = p.additional_income || {};
                    const hasCapGains = inc.capital_gains === true || String(inc.capital_gains) === 'true';
                    const hasBusiness = emp.employment_type === 'self_employed' || emp.employment_type === 'business';
                    const hasForeignAssets = inc.foreign_income === true || String(inc.foreign_income) === 'true';
                    const hasMultipleSources = inc.rental_income || inc.interest_income || inc.other_income;

                    let itrForm = 'ITR-1 (Sahaj)';
                    let itrDesc = 'For salaried individuals with income up to ₹50L from salary, one house property, and other sources.';
                    let itrColor = '#059669';
                    let itrBg = '#ecfdf5';
                    let itrBorder = '#a7f3d0';

                    if (hasForeignAssets) {
                      itrForm = 'ITR-2';
                      itrDesc = 'For individuals with capital gains, foreign assets/income, or more than one house property.';
                      itrColor = '#0284c7';
                      itrBg = '#e0f2fe';
                      itrBorder = '#bae6fd';
                    } else if (hasCapGains) {
                      itrForm = 'ITR-2';
                      itrDesc = 'For individuals with capital gains from sale of shares, mutual funds, or property.';
                      itrColor = '#0284c7';
                      itrBg = '#e0f2fe';
                      itrBorder = '#bae6fd';
                    } else if (hasBusiness) {
                      itrForm = 'ITR-3';
                      itrDesc = 'For individuals or HUFs with income from business or profession.';
                      itrColor = '#d97706';
                      itrBg = '#fffbeb';
                      itrBorder = '#fde68a';
                    } else if (Number(taxReport.gross_total_income) > 5000000) {
                      itrForm = 'ITR-2';
                      itrDesc = 'Income exceeds ₹50L — ITR-1 is not applicable. Use ITR-2 for high-income salaried filers.';
                      itrColor = '#0284c7';
                      itrBg = '#e0f2fe';
                      itrBorder = '#bae6fd';
                    }

                    return (
                      <div className="tr-itr-section">
                        <div className="tr-itr-header">
                          <div className="tr-itr-icon">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                              <polyline points="14 2 14 8 20 8"/>
                              <line x1="12" y1="12" x2="12" y2="16"/>
                              <line x1="12" y1="18" x2="12.01" y2="18"/>
                            </svg>
                          </div>
                          <span className="tr-itr-label">Applicable ITR Form</span>
                        </div>
                        <div className="tr-itr-form-row">
                          <span className="tr-itr-badge">{itrForm}</span>
                        </div>
                        <p className="tr-itr-desc">{itrDesc}</p>
                      </div>
                    );
                  })()}
                </div>

                {/* ── RIGHT: Why this regime + Slab breakdown ── */}
                <div className="tax-report-card">
                  <div className="tr-card-header">
                    <div className="tr-card-icon tr-card-icon-green">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 8v4l3 3"/>
                      </svg>
                    </div>
                    <div>
                      <h2 className="tr-card-title">Regime Analysis</h2>
                      <p className="tr-card-subtitle">Recommendation & slab-by-slab breakdown</p>
                    </div>
                  </div>

                  {/* Explanation */}
                  <div className="tr-explanation">
                    <div className="tr-explanation-label">Why this regime?</div>
                    <p>{rec.explanation}</p>
                  </div>

                  {/* Slab breakdown */}
                  <details className="tr-slab-details" open>
                    <summary className="tr-slab-summary">Slab-by-slab breakdown</summary>
                    <div className="tr-slab-grid">
                      {['old', 'new'].map((k) => {
                        const r = k === 'old' ? oldR : newR;
                        return (
                          <div key={k} className="tr-slab-col">
                            <div className="tr-slab-col-title">{k === 'old' ? 'Old Regime' : 'New Regime'}</div>
                            {r.slab_breakdown.map((s, i) => (
                              <div key={i} className="tr-slab-row">
                                <span className="tr-slab-name">{s.slab}</span>
                                <span className="tr-slab-tax">{fmt(s.tax)}</span>
                              </div>
                            ))}
                            <div className="tr-slab-row tr-slab-total">
                              <span>Cess (4%)</span>
                              <span>{fmt(r.cess_4pct)}</span>
                            </div>
                            <div className="tr-slab-row tr-slab-total">
                              <span>Total Tax</span>
                              <span>{fmt(r.total_tax)}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </details>
                </div>

              </div>
              )}

              {activeTab === 'next-steps' && (
                <div className="tax-report-card tr-steps-card">
                  <div className="tr-card-header">
                    <div className="tr-card-icon tr-card-icon-green">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                        <polyline points="9 11 12 14 22 4"/>
                        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                      </svg>
                    </div>
                    <div>
                      <h2 className="tr-card-title">Your Next Steps</h2>
                      <p className="tr-card-subtitle">Based on your profile and recommended regime</p>
                    </div>
                  </div>

                  <ol className="tr-next-steps">
                    {nextSteps.map((step, i) => (
                      <li key={i} className="tr-step-item">
                        <div className="tr-step-num">{i + 1}</div>
                        <div className="tr-step-text">{step}</div>
                      </li>
                    ))}
                  </ol>

                  {/* Old regime deduction checklist — only shown if old is recommended */}
                  {(winner === 'old' || winner === 'tie') && (
                    <div className="tr-deduction-checklist">
                      <div className="tr-ded-checklist-title">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                          <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                        </svg>
                        Deductions to claim under Old Regime
                      </div>
                      {[
                        { label: 'Standard Deduction (Sec 16)', val: oldR.deductions.standard_deduction },
                        { label: 'HRA Exemption',               val: oldR.deductions.hra_exemption },
                        { label: 'Home Loan Interest (Sec 24b)',val: oldR.deductions.home_loan_sec24b },
                        { label: '80C Investments',             val: oldR.deductions.section_80c },
                        { label: '80D Health Insurance',        val: oldR.deductions.section_80d },
                        { label: '80CCD(1B) NPS',               val: oldR.deductions.nps_80ccd1b },
                      ].filter(d => d.val > 0).map((d, i) => (
                        <div key={i} className="tr-ded-item">
                          <span className="tr-ded-check">✓</span>
                          <span className="tr-ded-name">{d.label}</span>
                          <span className="tr-ded-amount">{fmt(d.val)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <a
                    href="https://www.incometax.gov.in/iec/foportal/"
                    target="_blank"
                    rel="noreferrer"
                    className="tr-portal-btn"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                      <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                    Open Income Tax Portal
                  </a>
                </div>
              )}

            </>
            );
          })()}

            {/* ── SERVICE GUIDANCE TAB ── */}
            {activeTab === 'service-guidance' && (
              <div className="sg-layout">

                {/* Left: Service selector + Documents */}
                <div className="tax-card sg-card">
                  <div className="card-header">
                    <div className="card-icon-wrapper">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                      </svg>
                    </div>
                    <div className="card-title-group">
                      <h2>Service &amp; Documents Setup</h2>
                      <p>Select service and manage your documents</p>
                    </div>
                  </div>

                  {/* Service Dropdown */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="sg-tax-function-select">
                      1. Select Tax Function / Operation
                    </label>
                    <div className="select-wrapper">
                      <select
                        id="sg-tax-function-select"
                        className="select-input"
                        value={selectedService}
                        onChange={(e) => { setSelectedService(e.target.value); setAssistancePlan(null); }}
                      >
                        <option value="" disabled>
                          {apiStatus === 'loading' ? 'Loading services...' : '-- Select tax function --'}
                        </option>
                        {servicesList.length > 0 ? (
                          servicesList.map((srv) => (
                            <option key={srv.id} value={srv.key || srv.id}>{srv.name}</option>
                          ))
                        ) : (
                          <>
                            <option value="itr-filing">ITR Filing (Income Tax Return)</option>
                            <option value="new-pan">New PAN Application</option>
                          </>
                        )}
                      </select>
                      <div className="select-arrow">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
                      </div>
                    </div>
                  </div>

                  {/* Document Input */}
                  <div className="form-group">
                    <label className="form-label" htmlFor="sg-doc-input">
                      2. Enter Documents You Have
                    </label>
                    <div className="input-with-button">
                      <input
                        id="sg-doc-input"
                        type="text"
                        className="text-input"
                        placeholder="Type document name (e.g. Form 16, Aadhaar)..."
                        value={docInput}
                        onChange={(e) => setDocInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                      />
                      <button type="button" className="add-doc-btn" onClick={() => handleAddDocument(docInput)}>+ Add</button>
                    </div>
                    <div className="suggestions-group">
                      <div className="suggestions-title">Quick Add Popular Documents</div>
                      <div className="suggestions-flex">
                        {suggestedDocs.map((sug) => {
                          const isAdded = documents.includes(sug);
                          return (
                            <button key={sug} type="button" className="quick-pill"
                              style={{ opacity: isAdded ? 0.5 : 1, cursor: isAdded ? 'default' : 'pointer' }}
                              onClick={() => !isAdded && handleAddDocument(sug)}>
                              {isAdded ? '✓ ' + sug : '+ ' + sug}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Added Documents */}
                  <div className="documents-container">
                    <div className="form-label">Added Documents ({documents.length})</div>
                    <div className="docs-tag-list">
                      {documents.length === 0 ? (
                        <div className="empty-docs-placeholder">No documents added yet.</div>
                      ) : (
                        documents.map((doc) => (
                          <span key={doc} className="doc-chip">
                            <svg className="doc-chip-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                              <polyline points="13 2 13 9 20 9" />
                            </svg>
                            {doc}
                            <button type="button" className="remove-chip-btn" onClick={() => handleRemoveDocument(doc)} title="Remove">✕</button>
                          </span>
                        ))
                      )}
                    </div>
                  </div>

                  {selectedService && (
                    <button type="button" className="action-btn-primary" onClick={handleGenerateGuidance} disabled={isSubmitting || isLoadingDetails}>
                      {isSubmitting ? <span>Analyzing Documents...</span>
                        : isLoadingDetails ? <span>Fetching AI details...</span>
                        : <><span>Get Tax Compass Guidance</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg></>}
                    </button>
                  )}
                </div>

                {/* Right: Assistant Guidance Overview */}
                <div className="tax-card sg-card guidance-panel">
                  <div className="card-header">
                    <div className="card-icon-wrapper" style={{ backgroundColor: '#ecfdf5', color: '#059669' }}>
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                        <polyline points="22 4 12 14.01 9 11.01" />
                      </svg>
                    </div>
                    <div className="card-title-group">
                      <h2>Assistant Guidance Overview</h2>
                      <p>Live details powered by AI Assistant</p>
                    </div>
                  </div>

                  {!selectedService ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: '#4a6fa5' }}>
                      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#93b9e8" strokeWidth="1.5" style={{ marginBottom: '12px' }}>
                        <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#1e3a5f', marginBottom: '6px' }}>Select a function to begin</h3>
                      <p style={{ fontSize: '0.85rem' }}>Choose a tax function from the left to see your document checklist and filing steps.</p>
                    </div>
                  ) : isLoadingDetails ? (
                    <div style={{ textAlign: 'center', padding: '40px 20px', color: '#0284c7' }}>
                      <p style={{ fontSize: '1rem', fontWeight: 600 }}>Fetching data from AI Assistant...</p>
                    </div>
                  ) : serviceDetails ? (
                    <>
                      <div className="service-status-banner active">
                        <div className="banner-text">
                          Service: <strong>{serviceDetails.name}</strong>
                          {serviceDetails.Official_Link && (
                            <div style={{ fontSize: '0.8rem', marginTop: '4px' }}>
                              Official Portal:{' '}
                              <a href={serviceDetails.Official_Link} target="_blank" rel="noreferrer" style={{ color: '#0284c7', textDecoration: 'underline' }}>
                                {serviceDetails.Official_Link}
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                      {serviceDetails.description && (
                        <p style={{ fontSize: '0.875rem', color: '#4a6fa5', marginBottom: '16px', fontStyle: 'italic' }}>
                          {serviceDetails.description}
                        </p>
                      )}
                      {serviceDetails.documents_required && (
                        <div>
                          <div className="checklist-title" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                              </svg>
                              <span>Required Documents Checklist</span>
                            </div>
                            {selectedService === 'itr-filing' && userProfile && (
                              <span className="badge-tag emerald" style={{ fontSize: '0.72rem', fontWeight: 600 }}>
                                Tailored to your profile
                              </span>
                            )}
                          </div>
                          <ul className="checklist-items">
                            {serviceDetails.documents_required.map((req) => {
                              const present = isDocPresent(req);
                              return (
                                <li key={req} className={`checklist-item ${present ? 'has-doc' : ''}`}>
                                  <div className="item-left">
                                    <span className={present ? 'status-icon-check' : 'status-icon-pending'}>{present ? '✓' : '!'}</span>
                                    <span>{req}</span>
                                  </div>
                                  <span className={`badge-tag ${present ? 'emerald' : 'amber'}`}>{present ? 'Available' : 'Required'}</span>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </>
                  ) : (
                    <div style={{ padding: '20px', color: '#ef4444' }}>Failed to load service details. Please ensure the backend server is running.</div>
                  )}
                </div>

                {/* Full-width: Step-by-Step Guidance + Videos */}
                {selectedService && serviceDetails && (
                  <div className="sg-steps-row">
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: assistancePlan?.roadmap?.tutorial_videos?.length > 0 ? 'repeat(auto-fit, minmax(340px, 1fr))' : '1fr',
                      gap: '24px', alignItems: 'start',
                    }}>
                      {(assistancePlan?.roadmap?.completion_path || assistancePlan?.roadmap?.guidance || serviceDetails.guidance) && (
                        <div className="steps-box" style={{ marginTop: 0 }}>
                          <div className="steps-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 17 22 12" />
                              </svg>
                              <span>{assistancePlan?.roadmap ? 'AI Agent Guidance Roadmap' : 'Step-by-Step Procedure'}</span>
                            </div>
                            {assistancePlan?.roadmap && <span className="badge-tag emerald" style={{ fontSize: '0.75rem' }}>Agent Dynamic Guidance</span>}
                          </div>
                          {(assistancePlan?.roadmap?.completion_path || assistancePlan?.roadmap?.guidance || serviceDetails.guidance).map((step, idx) => {
                            const parsed = parseStepItem(step, idx);
                            if (!parsed.isAcquisition) {
                              return (
                                <div key={idx} className="step-row">
                                  <div className="step-num">{parsed.stepNumber}</div>
                                  <div className="step-content">
                                    <h4>Step {parsed.stepNumber}</h4>
                                    <p>{renderTextWithLinks(parsed.text)}</p>
                                  </div>
                                </div>
                              );
                            }
                            const isExpanded = Boolean(openGuides[idx]);
                            return (
                              <div key={idx} className="step-row" style={{ alignItems: 'flex-start' }}>
                                <div className="step-num">{parsed.stepNumber}</div>
                                <div className="step-content" style={{ width: '100%' }}>
                                  <div style={{ borderRadius: '12px', border: '1px solid rgba(96,165,250,0.3)', backgroundColor: '#0f2a56', overflow: 'hidden', width: '100%' }}>
                                    <button type="button" onClick={() => toggleGuide(idx)} style={{
                                      width: '100%', padding: '12px 16px', display: 'flex', alignItems: 'center',
                                      justifyContent: 'space-between', background: 'linear-gradient(135deg,#0f2a56,#1a3f7a)',
                                      border: 'none', color: '#fff', cursor: 'pointer', fontSize: '0.92rem', fontWeight: 700, textAlign: 'left',
                                    }}>
                                      <span style={{ color: '#7dd3fc' }}>{parsed.title}</span>
                                      <span style={{ fontSize: '0.85rem', color: '#93c5fd', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
                                    </button>
                                    {isExpanded && (
                                      <div style={{ padding: '16px', borderTop: '1px solid rgba(96,165,250,0.25)' }}>
                                        {parsed.source && (
                                          <div style={{ fontSize: '0.8rem', color: '#93c5fd', marginBottom: '14px', backgroundColor: '#0f2a56', padding: '8px 12px', borderRadius: '8px', border: '1px solid rgba(96,165,250,0.25)' }}>
                                            <strong style={{ color: '#7dd3fc' }}>Official Source:</strong> {renderTextWithLinks(parsed.source)}
                                          </div>
                                        )}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                          {parsed.subSteps.map((subStep, subIdx) => (
                                            <div key={subIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                                              <span style={{ width: '22px', height: '22px', borderRadius: '50%', background: 'linear-gradient(135deg,#38bdf8,#60a5fa)', color: '#fff', fontSize: '0.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: '2px', boxShadow: '0 2px 6px rgba(56,189,248,0.4)' }}>{subIdx + 1}</span>
                                              <div style={{ fontSize: '0.85rem', color: '#bfdbfe', lineHeight: '1.5' }}>{renderTextWithLinks(subStep)}</div>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {assistancePlan?.roadmap?.tutorial_videos?.length > 0 && (
                        <div className="steps-box" style={{ marginTop: 0, background: 'linear-gradient(145deg,#e0f2fe 0%,#f0f9ff 100%)', border: '1px solid #bae6fd', boxShadow: '0 4px 16px rgba(14,165,233,0.12)' }}>
                          <div className="steps-header" style={{ color: '#0284c7' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                              <span>Recommended Video Tutorials</span>
                            </div>
                          </div>
                          {assistancePlan.roadmap.tutorial_videos.map((vid, idx) => (
                            <div key={idx} className="step-row" style={{ borderLeftColor: '#0ea5e9' }}>
                              <div className="step-num" style={{ background: 'linear-gradient(135deg,#0ea5e9,#38bdf8)', color: '#fff' }}>🎥</div>
                              <div className="step-content">
                                <h4 style={{ color: '#0c4a6e' }}>{vid.title}</h4>
                                <p style={{ margin: '4px 0', fontSize: '0.85rem', color: '#0369a1' }}>Channel: <strong>{vid.channel}</strong></p>
                                <a href={vid.url} target="_blank" rel="noreferrer" style={{ color: '#0284c7', textDecoration: 'underline', fontSize: '0.85rem', fontWeight: 600 }}>Watch Tutorial →</a>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

        </div>
      </section>
      )}


      {/* Footer */}
      <footer className="app-footer">
        <p>© {new Date().getFullYear()} Tax Compass. Disclaimer: Content and official guidelines may change over time. We are just here to help guide your tax processes.</p>
        <div className="footer-links">
          <a href="#privacy">Privacy & Security</a>
          <a href="#help">Income Tax FAQs</a>
          <a href="#support">Contact Tax Support</a>
        </div>
      </footer>
    </div>
  );
}