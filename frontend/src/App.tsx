import React from 'react';
import LegacyApp from './LegacyApp';
export function App() {
  const connected = new URLSearchParams(window.location.search).get('connected') === '1';
  if (connected) return <div><button style={{position:'fixed',zIndex:1000,top:8,right:12,padding:'8px 12px',background:'#a84d1c',color:'#fff',border:0,cursor:'pointer'}} onClick={()=>{window.location.href='/'}}>← Voltar ao projeto demonstrativo</button><LegacyApp /></div>;
  return <iframe title="BIM SCHEDULE — Projeto demonstrativo" src="/demo.html" style={{width:'100%',height:'100vh',border:0,display:'block'}} />;
}
export default App;
