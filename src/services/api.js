export async function api(path,{token,body,...options}={}){
  const response=await fetch(`/api${path}`,{...options,headers:{...(body?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined})
  if(response.status===204)return null
  const payload=await response.json().catch(()=>({}))
  if(!response.ok)throw new Error(typeof payload.detail==='string'?payload.detail:'Request failed')
  return payload
}
