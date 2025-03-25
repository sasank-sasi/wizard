from typing import Dict, Any, Optional, List
import json
import os
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings  # Updated import
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from groq import Groq
from fastapi import HTTPException
import torch
import faiss

class MeetingRAG:
    def __init__(self, groq_client: Groq):
        """Initialize the RAG system"""
        self.groq_api_key = groq_client.api_key
        
        # Check GPU availability
        self.use_gpu = torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"
        logging.info(f"Using device: {self.device} for embeddings")
        
        # Initialize ChatGroq with model kwargs for llama3
        self.llm = ChatGroq(
            groq_api_key=self.groq_api_key,
            model_name="llama3-8b-8192",
            temperature=0.1,
            max_tokens=8192,
            model_kwargs={
                "top_p": 0.9,
                "stream": False
            }
        )
        
        # Enhanced QA prompt template
        self.qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an AI assistant specialized in analyzing meeting transcripts. "
                      "Use the following context to answer questions about the meeting:\n\n"
                      "{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        
        # Initialize embeddings with device configuration
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={"device": self.device}
        )
        
        # Initialize FAISS resources
        if self.use_gpu:
            self.gpu_resources = faiss.StandardGpuResources()
            logging.info("Initialized FAISS GPU resources")
        
        # Initialize storage and text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        self.vectorstores: Dict[str, Any] = {}
        self.memories: Dict[str, ConversationBufferMemory] = {}
        
    async def load_meeting_data(self, meeting_id: str) -> bool:
        """Load meeting data into vector store"""
        try:
            if (meeting_id in self.vectorstores):
                return True
                
            # Normalize meeting_id: replace spaces with underscores and convert to lowercase
            normalized_id = meeting_id.replace(' ', '_').lower()
            
            # Find the latest JSON file for this meeting
            output_dir = os.path.join(os.getcwd(), "output")
            
            # List all JSON files in the output directory
            all_files = [f for f in os.listdir(output_dir) if f.endswith('.json')]
            logging.info(f"Available files: {all_files}")
            
            # Try different filename patterns
            patterns = [
                normalized_id,                    # annual_meeting
                meeting_id.replace(' ', '_'),     # annual_meeting
                meeting_id,                       # annual meeting
                meeting_id.lower(),              # annual meeting
            ]
            
            files = []
            for pattern in patterns:
                files.extend([
                    f for f in all_files 
                    if f.startswith(pattern) or f.startswith(pattern.replace(' ', '_'))
                ])
                
            if not files:
                logging.error(f"No meeting data found for ID: {meeting_id}")
                logging.error(f"Tried patterns: {patterns}")
                return False
            
            # Get the most recent file
            latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(output_dir, x)))
            file_path = os.path.join(output_dir, latest_file)
            
            logging.info(f"Loading meeting data from: {latest_file}")
            
            # Load and prepare the data
            with open(file_path, 'r') as f:
                meeting_data = json.load(f)
            
            # Prepare context by combining relevant fields
            context = self._prepare_context(meeting_data)
            
            # Split text and create vectorstore
            texts = self.text_splitter.split_text(context)
            
            # Create FAISS index
            vectorstore = FAISS.from_texts(
                texts, 
                self.embeddings,
                normalize_L2=True  # L2 normalization for better GPU performance
            )
            
            # Move index to GPU if available
            if self.use_gpu:
                try:
                    index = vectorstore.index
                    index_flat_gpu = faiss.index_cpu_to_gpu(self.gpu_resources, 0, index)
                    vectorstore.index = index_flat_gpu
                    logging.info("FAISS index moved to GPU")
                except Exception as gpu_error:
                    logging.warning(f"Failed to move index to GPU: {str(gpu_error)}")
            
            self.vectorstores[meeting_id] = vectorstore
            
            # Initialize conversation memory
            self.memories[meeting_id] = ConversationBufferMemory(
                memory_key="chat_history",
                output_key="answer",  # Match the output_key from the chain
                return_messages=True
            )
            
            logging.info(f"Successfully loaded meeting data for ID: {meeting_id}")
            return True
            
        except Exception as e:
            logging.error(f"Error loading meeting data: {str(e)}")
            return False
    
    def _prepare_context(self, meeting_data: Dict[str, Any]) -> str:
        """Prepare meeting context from JSON data"""
        sections = [
            f"Full Transcript:\n{meeting_data['transcript']}"
            "Key Points:\n" + "\n".join([f"- {point}" for point in meeting_data['key_points']]),
            "Action Items:\n" + "\n".join([f"- {item}" for item in meeting_data['action_items']]),
            f"Participants: {', '.join(meeting_data['participants'])}",
            "Follow-up Items:\n" + "\n".join([f"- {item}" for item in meeting_data['follow_up']]),
            "Important Dates:\n" + "\n".join([f"- {date}" for date in meeting_data['dates']]),
            f"Next Steps:\n{meeting_data['next_steps']}",
            f"Meeting Summary:\n{meeting_data['summary']}\n",
        ]
        return "\n\n".join(sections)
    
    async def answer_question(self, meeting_id: str, question: str) -> Dict[str, Any]:
        """Answer a question about the meeting"""
        try:
            if meeting_id not in self.vectorstores:
                if not await self.load_meeting_data(meeting_id):
                    raise ValueError(f"Meeting data not found for ID: {meeting_id}")
            
            vectorstore = self.vectorstores[meeting_id]
            memory = self.memories[meeting_id]
            
            # Create retrieval chain with proper configuration
            chain = ConversationalRetrievalChain.from_llm(
                llm=self.llm,
                retriever=vectorstore.as_retriever(
                    search_kwargs={"k": 3}
                ),
                memory=memory,
                combine_docs_chain_kwargs={
                    "prompt": self.qa_prompt,
                    "document_variable_name": "context"
                },
                get_chat_history=lambda h: h,
                return_source_documents=True,
                verbose=True,
                output_key="answer"  # Specify output key for memory
            )
            
            # Get answer using ainvoke
            response = await chain.ainvoke({
                "question": question,
                "chat_history": memory.chat_memory.messages
            })
            
            # Log the interaction
            logging.info(f"Question answered for meeting {meeting_id}: {question[:100]}...")
            
            return {
                "answer": response['answer'],
                "sources": [doc.page_content[:200] + "..." for doc in response['source_documents']]
            }
            
        except Exception as e:
            logging.error(f"Error answering question: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to answer question: {str(e)}"
            )
    
    async def clear_meeting_context(self, meeting_id: str) -> bool:
        """Clear the conversation history for a meeting"""
        try:
            if meeting_id in self.memories:
                self.memories[meeting_id].clear()
                logging.info(f"Cleared conversation history for meeting: {meeting_id}")
            return True
        except Exception as e:
            logging.error(f"Error clearing meeting context: {str(e)}")
            return False

    async def cleanup(self):
        """Clean up GPU resources"""
        try:
            if self.use_gpu:
                for vectorstore in self.vectorstores.values():
                    if hasattr(vectorstore, 'index'):
                        # Move index back to CPU before deletion
                        index_cpu = faiss.index_gpu_to_cpu(vectorstore.index)
                        vectorstore.index = index_cpu
                logging.info("GPU resources cleaned up")
        except Exception as e:
            logging.error(f"Error during cleanup: {str(e)}")