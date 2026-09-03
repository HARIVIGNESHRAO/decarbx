const API_BASE_URL=(import.meta.env.VITE_API_BASE_URL||'').replace(/\/$/,'')

export async function api(path,{token,body,...options}={}){
  const response=await fetch(`${API_BASE_URL}/api${path}`,{...options,headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined})
  if(response.status===204)return null
  const text=await response.text()
  let payload
  try{payload=text?JSON.parse(text):{}}catch{payload={}}
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:`API request failed (${response.status})`)
  return payload
}
