export const STUDENT_ID = "demo_student";

export function getThreadId(): string {
  const key = "vitian_thread_id";
  let threadId = localStorage.getItem(key);
  if (!threadId) {
    threadId = "demo_thread_" + Math.floor(Math.random() * 1000000);
    localStorage.setItem(key, threadId);
  }
  return threadId;
}

export const TOPICS = [
  "DSA", 
  "DBMS", 
  "OS", 
  "Computer Networks", 
  "System Design", 
  "Aptitude", 
  "Verbal Ability", 
  "Logical Reasoning",
  "React",
  "Node.js",
  "Python"
];
