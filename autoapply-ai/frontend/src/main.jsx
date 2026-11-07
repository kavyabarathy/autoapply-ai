import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import Auth from "./Auth.jsx";
import { clearToken, getToken } from "./api.js";
import "./index.css";

function Root() {
  const [signedIn, setSignedIn] = useState(Boolean(getToken()));
  if (!signedIn) return <Auth onAuth={() => setSignedIn(true)} />;
  return (
    <App
      onLogout={() => {
        clearToken();
        setSignedIn(false);
      }}
    />
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<Root />);
