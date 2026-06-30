/* ESLD Admin — shared data layer across all admin-*.html pages
   TODO: replace every getData()/setData() pair with Firebase Firestore
   reads/writes (collections: teachers, students, parents, classes, settings)
   once the backend is wired up. Keys/shapes are kept Firestore-friendly. */

const $ = (s) => document.querySelector(s);

/* ---------- Session guard ---------- */
let session = null;
try { session = JSON.parse(localStorage.getItem('esld-session') || 'null'); } catch(e){}
if(!session || session.role !== 'admin'){
  session = { role:'admin', id:'AID-DEMO-01', name:'Demo Admin', schoolName:'ESLD Demo School', schoolCode:'DEMO01' };
}

function initSidebarIdentity(){
  const nameEl = $('#adminNameMini'), schoolEl = $('#adminSchoolMini'), avEl = $('#adminAvatar');
  const tagEl = $('#schoolTag'), aidEl = $('#topbarAid');
  if(nameEl) nameEl.textContent = session.name;
  if(schoolEl) schoolEl.textContent = session.schoolName;
  if(avEl) avEl.textContent = (session.name||'A').trim()[0].toUpperCase();
  if(tagEl) tagEl.textContent = `${session.schoolName} · ${session.schoolCode}`;
  if(aidEl) aidEl.textContent = session.id;
}

function logout(){
  localStorage.removeItem('esld-session');
  toast('Logged out.');
  setTimeout(()=> window.location.href = 'role-selection.html', 600);
}

function toggleSidebar(){ document.getElementById('sidebar').classList.toggle('open'); }

/* ---------- Generic storage helpers ---------- */
function getData(key){ try{ return JSON.parse(localStorage.getItem(key)||'[]'); } catch(e){ return []; } }
function setData(key, arr){ localStorage.setItem(key, JSON.stringify(arr)); }

const K_TEACHERS = 'esld-admin-teachers';
const K_STUDENTS = 'esld-admin-students';
const K_PARENTS  = 'esld-admin-parents';
const K_CLASSES  = 'esld-admin-classes';
const K_SETTINGS = 'esld-admin-settings';

function toast(msg, type=''){
  const t = $('#toast');
  if(!t) return;
  t.textContent = msg;
  t.className = 'toast show' + (type ? ' '+type : '');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(()=> t.classList.remove('show'), 2800);
}

/* ---------- Seed demo data on first load ---------- */
function seedIfEmpty(){
  if(getData(K_TEACHERS).length === 0){
    setData(K_TEACHERS, [
      { tid:'TID001', name:'Anita Krishnan', subject:'Special Education', email:'anita.k@demo.esld', mobile:'9811122233' },
      { tid:'TID002', name:'Rahul Mehta', subject:'Mathematics Support', email:'rahul.m@demo.esld', mobile:'9822233344' },
      { tid:'TID003', name:'Sara Thomas', subject:'Language & Reading', email:'sara.t@demo.esld', mobile:'9833344455' },
    ]);
  }
  if(getData(K_STUDENTS).length === 0){
    setData(K_STUDENTS, [
      { sid:'SID001', name:'Aarav Singh', classGrade:'5-A', need:'Dyslexia', teacherTid:'TID003', accuracy:78, coins:420, active:true },
      { sid:'SID002', name:'Diya Patel', classGrade:'6-B', need:'Dysgraphia', teacherTid:'TID001', accuracy:64, coins:310, active:true },
      { sid:'SID003', name:'Kabir Rao', classGrade:'4-A', need:'ADHD', teacherTid:'TID002', accuracy:45, coins:150, active:false },
      { sid:'SID004', name:'Meera Iyer', classGrade:'7-C', need:'Dyscalculia', teacherTid:'TID002', accuracy:38, coins:90, active:false },
      { sid:'SID005', name:'Vivaan Joshi', classGrade:'5-A', need:'Dyslexia', teacherTid:'TID003', accuracy:91, coins:610, active:true },
      { sid:'SID006', name:'Ira Nair', classGrade:'6-B', need:'ADHD', teacherTid:'TID001', accuracy:88, coins:540, active:true },
    ]);
  }
  if(getData(K_PARENTS).length === 0){
    setData(K_PARENTS, [
      { pid:'PID001', name:'Suresh Singh', mobile:'9900011122', studentSid:'SID001' },
      { pid:'PID002', name:'Kavya Patel', mobile:'9900022233', studentSid:'SID002' },
    ]);
  }
  if(getData(K_CLASSES).length === 0){
    setData(K_CLASSES, [
      { className:'5', section:'A' }, { className:'6', section:'B' }, { className:'4', section:'A' }, { className:'7', section:'C' },
    ]);
  }
  if(!localStorage.getItem(K_SETTINGS)){
    localStorage.setItem(K_SETTINGS, JSON.stringify({
      schoolName: session.schoolName, schoolCode: session.schoolCode, academicYear:'2026-2027', academicStatus:'Active', logo:null
    }));
  }
}
seedIfEmpty();

/* ---------- ID generators ---------- */
function nextId(prefix, list, key){
  const nums = list.map(x => parseInt((x[key]||'').replace(prefix,''),10)).filter(n=>!isNaN(n));
  const next = (nums.length ? Math.max(...nums) : 0) + 1;
  return prefix + String(next).padStart(3,'0');
}

/* ---------- Run on every page load ---------- */
document.addEventListener('DOMContentLoaded', initSidebarIdentity);
document.addEventListener('click', (e)=>{
  document.querySelectorAll('.modal-overlay').forEach(o => { if(e.target===o) o.classList.remove('show'); });
});
function closeModal(id){ $('#'+id).classList.remove('show'); }