# Research

## What I needed to learn or learned

I needed to learn about webhooks and how they are different from cron jobs and REST API, i also needed to learn how to implement one.

For ticket classification i needed to learn the best approches based on research to build or finetune an ML model.

I am learning about containers management and how to further use Docker compose, because i implemented this technology only once in the Deskline AI assisstant but i am noot sure of my skills in it, so i am still working on that.

I learned about idempotency. For example, when a webhook is sent to a system but the sender doesn't receive a confirmation, it may send the same webhook again. Without idempotency, the system might process the same event twice. By using an idempotency key, the system can recognise that the event has already been processed and avoid repeating the operation. Idempotency makes retries safe. When a request fails, times out, or gets delivered more than once, the system can retry without accidentally repeating its effects.

I learned about pydantic, it is kind of similar to the validation models that i was building in Laravel (the M in MVC) and mongoose in MongoDB, prisma in nodejs and so on, used for assisting with data validation. Well for this prototype i am not using regular expressions, although i used enums i am using only strings.

I have learned the difference between polling, webhooks and cron jobs. Polling is the system repeatedly asks an external service whether an operation has finished or whether new information is available, at regular intervals. webhook is when a system is configured to send automatic notifications to another system when a specific event occurs, such as a new support ticket being created. cron jobs: a task is scheduled to run automatically at specified times or intervals, using a schedule such as a cron expression.

I already know XML and Json, but this is the first time i delt with a ymal file, so i tried to understand the difference between the three. i used ymal to be maintainable as well. 

I learned how to load a model and how to use it for real predictions and how can a classical ML model be integrated into a real system.

I also remembered how we used to do networking in distributed systems ( The intake API and the worker are both clients of PostgreSQL. The AI assistant is the client of the intake API, and the API is the server for that assistant.

The assistant sends the escalated ticket to the intake route. The API validates it and inserts a queued row. The assistant then keeps calling the status route with the ticket id. Both of those routes are served by the same FastAPI process.

The worker never receives that HTTP call. It reads and updates the same PostgreSQL rows: claim the queued ticket, run inference, store the decision. The assistant’s next status call reads that decision back through the API.

One more client relationship sits beside those two. After the decision is stored, the worker is an HTTP client of the webhook receiver. It posts the outcome to WEBHOOK_URL. The webhook process is the server for that notification).

I gained an in depth knowledge of docker. I even learned how to publish images. i fimilarised myself with the commands, the terminology, the files and so on. My knowledge in how operating systems work has helped immensely.

## Where I looked

For the webhooks i watched some youtube videos explaining that [Webhook vs Websocket](https://youtu.be/1hE-bLSCcDQ?si=MndNaDJ-GyKqk1rN), [REST API (HTTP) vs Websockets](https://youtu.be/fG4dkrlaZAA?si=L_98Jtu3Y4gAxvw-) ...

For ticket classification i read this paper to decide on the important decisions concerning the classifier: [Ticket automation: An insight into current research with applications to multi-level classification scenarios](https://www.sciencedirect.com/science/article/pii/S0957417423004864?fr=RR-2&ref=pdf_download&rr=a519a7941b17631d)

For containers management i will be using Docker documentation along side AI to help me understand concepts better implement the technology in my code.

Idempotency: https://chatgpt.com/share/6ae1f984-af0c-83eb-be4b-aaef6a33df7f

Pydantic: just asked my code pilot to explain it for me, it is pretty easy.

polling vs cron vs webhooks: https://chatgpt.com/share/6ae33cd1-3c14-83ed-b1e6-a9e23d1d85ca

## How I judged it

I always try to understand the user needs, define the scope and then design the system architecture as a whole before writing a single line of code, and i run thought experiments using my knoweledge to first imagine the modes of failures and whether a component is really necessary for the system, i try to find the minimal design or solution possible before coding anything. I use diagrams to keep everything clear and keep track of my design solutions.

I used AI (cursor) to help me with the coding phase, that is why i was able to deliver many functionalities of this project, but my approach was i tell it what to write in each code file as components and then read the code closely and try to make sure it satisfies its purpose and i reflect on the code as a whole how that specific piece of code will affect the entirety of that component that i am building. 

## What failed

Well, my approach changed several times while I was building this project. One of those changes was priority. At first I assigned it by matching strings in the ticket text. I dropped that and predicted priority as well, with a second head on the classifier.

The other recurring problem was Python import paths, because the Docker image and a process started from the repository do not see the packages in the same place. In the image, desktriage_common sits directly under /app, next to the API or the worker. In the repository, that package lives inside the common/ folder, so a local process cannot import it until common is on PYTHONPATH.

I kept common as its own folder. When I ran a component locally without its image, I changed only the environment variables for that process: PYTHONPATH, so the imports resolve, and DATABASE_URL, so it reaches PostgreSQL on 127.0.0.1 instead of the Compose host name db. I am not sure that was the best way to support both layouts. (feedback please hhh).

