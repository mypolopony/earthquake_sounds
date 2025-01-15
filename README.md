Proposed Sequence Evaluation

**Small EC2 Hot Standby:**

Running the websocket and doing basic preprocessing is a good choice for keeping latency low and handling real-time traffic.

This ensures you have a dedicated, always-available endpoint for incoming data.
SQS or Kinesis:

Excellent for decoupling the processing stages and ensuring reliable data delivery.
SQS: Best if the data is discrete (e.g., messages) and doesn’t require ordering or real-time consumption.

**Kinesis: Ideal if ordering matters, or if you need real-time, multi-consumer data processing.


Lambda for Signal Processing:

Great for scaling processing tasks and keeping compute costs low.
Allows you to scale with demand and handle workloads independently from the EC2 instance.