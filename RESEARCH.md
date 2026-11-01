# Research

## What I needed to learn

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


## Where I looked

For the webhooks i watched some youtube videos explaining that [Webhook vs Websocket](https://youtu.be/1hE-bLSCcDQ?si=MndNaDJ-GyKqk1rN), [REST API (HTTP) vs Websockets](https://youtu.be/fG4dkrlaZAA?si=L_98Jtu3Y4gAxvw-) ...

For ticket classification i read this paper to decide on the important decisions concerning the classifier: [Ticket automation: An insight into current research with applications to multi-level classification scenarios](https://www.sciencedirect.com/science/article/pii/S0957417423004864?fr=RR-2&ref=pdf_download&rr=a519a7941b17631d)

For containers management i will be using Docker documentation along side AI to help me understand concepts better implement the technology in my code.

Idempotency: https://chatgpt.com/share/6ae1f984-af0c-83eb-be4b-aaef6a33df7f

Pydantic: just asked my code pilot to explain it for me, it is pretty easy.

polling vs cron vs webhooks: https://chatgpt.com/share/6ae33cd1-3c14-83ed-b1e6-a9e23d1d85ca

## How I judged it



## What failed

## What I learned


