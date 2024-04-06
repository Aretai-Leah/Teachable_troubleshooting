Useage Guide. 

Start Litellm.  litellm --config litellm_config --debug    

Run api_scheduler_03

This will start the scheduled tasks, including Reading and Goals. 

to call directly, use postman. 

POST: http://127.0.0.1:5000/api/message
    {
    "interlocutor":"<some person>",
    "message": "<some message."
    }

Logs are located in the Logs db
The teachability db is in the memory dir
The chroma_memory functions script just outputs all memos. 
The problem is with Memo 162, which doesn't exist.  
The extracted logs for troubleshooting text file contains the adjacent entries from the AG db.  This corresponds to about entry 860 in the AG Logs

The input text at the time was excerpts from the book Snow Crash.  
The model being used was Claude 3 Opus.

    
