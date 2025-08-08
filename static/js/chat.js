let socket = null;
function initChat(user){
  if(socket) return;
  socket = io();
  socket.on('connect', ()=>{
    socket.emit('join',{user});
  });
  socket.on('message', (msg)=>{
    appendMessage(msg);
  });
  socket.on('status', (s)=>{
    appendStatus(s.msg);
  });

  document.getElementById('send-btn').addEventListener('click', ()=>{
    sendMsg(user);
  });
  document.getElementById('msg-input').addEventListener('keydown', (e)=>{
    if(e.key==='Enter') sendMsg(user);
  });

  // load history
  fetch('/chat_history').then(r=>r.json()).then(data=>{
    if(data.ok){
      data.history.forEach(appendMessage);
    }
  });
}

function sendMsg(user){
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if(!text) return;
  socket.emit('message',{user, text});
  input.value = '';
}

function appendMessage(msg){
  const box = document.getElementById('messages');
  const el = document.createElement('div');
  el.innerHTML = `<div><strong>${msg.user}</strong> <small>${new Date(msg.ts).toLocaleTimeString()}</small><div>${msg.text}</div></div><hr>`;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function appendStatus(s){
  const box = document.getElementById('messages');
  const el = document.createElement('div');
  el.innerHTML = `<em>${s}</em><hr>`;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}
