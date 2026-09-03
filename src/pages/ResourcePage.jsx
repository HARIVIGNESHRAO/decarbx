import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Database, Plus } from 'lucide-react'
import { api } from '../services/api'

export default function ResourcePage({token,title,resource,user}){
 const [records,setRecords]=useState(null),[error,setError]=useState(''),[form,setForm]=useState({name:'',description:''})
 const load=useCallback(()=>api(`/resources/${resource}`,{token}).then(setRecords).catch(e=>setError(e.message)),[resource,token])
 useEffect(()=>{load()},[load])
 const submit=async e=>{e.preventDefault();try{await api(`/resources/${resource}`,{token,method:'POST',body:{data:form}});setForm({name:'',description:''});load()}catch(err){setError(err.message)}}
 const writable=user.permissions.includes('resources:write')&&resource!=='audit-trail'
 return <section className="resource-page"><header className="module-header"><div><p className="eyebrow">Nexgile-DecarbX platform</p><h1>{title}</h1><p>Organization-scoped records loaded directly from MongoDB.</p></div></header>{writable&&<form className="resource-form panel" onSubmit={submit}><input placeholder={`${title} name`} value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required/><input placeholder="Description or details" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/><button className="export-button"><Plus/>Create</button></form>}{error?<div className="module-state error"><AlertTriangle/><strong>{error}</strong></div>:records===null?<div className="module-state"><Database/>Loading MongoDB data…</div>:<article className="panel resource-list">{records.map(item=><div key={item.id}><strong>{item.name||item.activity_type||item.action||item.id}</strong><span>{item.description||item.status||item.scope||item.object_type||'Stored record'}</span><small>{item.created_at?.slice(0,10)||item.timestamp?.slice(0,10)||''}</small></div>)}{!records.length&&<div className="empty-state">No {title.toLowerCase()} records in MongoDB.</div>}</article>}</section>
}
