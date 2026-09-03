import { useEffect, useState } from 'react'
import { CheckCircle2, Database, FileText, Plus, RefreshCw, Search, ShieldAlert } from 'lucide-react'

const slugs={'Carbon accounting':'carbon-accounting','Product footprint':'product-footprint','Suppliers':'suppliers','Reduction planning':'reduction-planning','Data & integrations':'data-integrations','Reports & disclosures':'reports-disclosures'}

export default function ModulePage({name,token}){
  const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[query,setQuery]=useState(''),[refresh,setRefresh]=useState(0)
  useEffect(()=>{fetch(`/api/modules/${slugs[name]}`,{headers:{Authorization:`Bearer ${token}`}}).then(r=>{if(!r.ok)throw new Error('Could not load this module');return r.json()}).then(setData).catch(e=>setError(e.message)).finally(()=>setLoading(false))},[name,token,refresh])
  const reload=()=>{setLoading(true);setError('');setRefresh(x=>x+1)}
  if(loading)return <div className="module-state"><RefreshCw className="spin"/><strong>Loading {name}…</strong></div>
  if(error)return <div className="module-state error"><ShieldAlert/><strong>{error}</strong><button onClick={reload}>Try again</button></div>
  const rows=data.rows.filter(row=>row.some(cell=>String(cell).toLowerCase().includes(query.toLowerCase())))
  return <section className="module-page">
    <header className="module-header"><div><p className="eyebrow">Nexgile Industries / {name}</p><h1>{data.title}</h1><p>{data.description}</p></div><div><button className="secondary-action" onClick={reload}><RefreshCw/>Refresh</button>{data.access.can_write&&<button className="export-button"><Plus/>Add record</button>}</div></header>
    <div className="module-stats">{data.stats.map((stat,index)=><article key={stat.label}><span className={`module-stat-icon tone-${index}`} >{index===0?<Database/>:index===1?<CheckCircle2/>:<FileText/>}</span><div><small>{stat.label}</small><strong>{stat.value}</strong></div></article>)}</div>
    <article className="panel module-table-panel"><div className="module-table-head"><div><h2>{data.title} records</h2><p>Live data from MongoDB · Access: {data.access.role}</p></div><label><Search/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search records"/></label></div><div className="table-wrap"><table className="module-table"><thead><tr>{data.columns.map(column=><th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index}>{row.map((cell,cellIndex)=><td key={cellIndex}>{cellIndex===row.length-1?<span className={`record-status ${String(cell).toLowerCase().replaceAll(' ','-')}`}>{cell}</span>:cell}</td>)}</tr>)}</tbody></table>{!rows.length&&<div className="empty-state">No matching records found.</div>}</div></article>
  </section>
}
