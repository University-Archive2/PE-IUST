from typing import Dict, List
import simpy
import random


class Config:
    def __init__(self):
        self.arrival_rate = 1.0
        self.mu_1 = 2.0
        self.mu_2 = 4.0
        self.mu_3 = 3.0


class Queue:
    def __init__(self, env, mu):
        self.env = env
        self.server = simpy.Resource(env, capacity=1)
        self.mu = mu
        self.num_serviced = 0
        self.num_in_queue = 0
        self.total_delay = 0
        self.times_of_arrival = []
        self.service_times = []
        self.area_under_b = 0  # sum active time
        self.area_under_q = 0  # sum in queue by time
        self.last_event_time = 0
        self.server_status = 0

    def process(self):
        self.times_of_arrival.append(self.env.now)

        self.num_serviced += 1
        self.num_in_queue += 1
        self.update_stats()

        with self.server.request() as request:
            yield request

            self.total_delay += self.env.now - self.times_of_arrival.pop(0)

            self.num_in_queue -= 1
            self.update_stats()

            service_time = random.expovariate(self.mu)
            yield self.env.timeout(service_time)
            self.service_times.append(service_time)

            self.update_stats()

    def update_stats(self):
        time_since_last_event = self.env.now - self.last_event_time
        self.last_event_time = self.env.now

        self.area_under_b += time_since_last_event * self.server_status
        self.area_under_q += time_since_last_event * self.num_in_queue

        self.server_status = int(not self.server_status)


class Customer:
    def __init__(
        self, env: simpy.Environment, queues: Dict[str, Queue], config: Config
    ):
        self.env = env
        self.queues = queues
        self.config = config

    def process(self):
        while True:
            inter_arrival_time = random.expovariate(self.config.arrival_rate)
            yield self.env.timeout(inter_arrival_time)
            yield self.env.process(self.queues["1"].process())

            if random.random() < 0.4:
                next_queue = "2"
            else:
                next_queue = "3"

            yield self.env.process(self.queues[next_queue].process())


class Simulation:
    def __init__(self, config: Config, env=simpy.Environment()):
        self.env = env
        self.config = config
        self.queues = {
            "1": Queue(self.env, config.mu_1),
            "2": Queue(self.env, config.mu_2),
            "3": Queue(self.env, config.mu_3),
        }

    def run(self):
        c = Customer(self.env, self.queues, self.config)
        self.env.process(c.process())
        self.env.run(until=10)

        (
            avg_num_customers_in_queue,
            avg_residence_time_in_queue,
            avg_num_customers_waiting_in_queue,
            avg_time_spent_waiting_in_queue,
            utilization_rate,
        ) = self.calculate_metrics(self.queues, 10)

        print(
            f"Average Number of Customers in Queue (Li): {avg_num_customers_in_queue}"
        )
        print(
            f"Average Number of Customers Waiting in Queue (LQi): {avg_num_customers_waiting_in_queue}"
        )
        print(f"Average Residence Time in Queue (Wi): {avg_residence_time_in_queue}")
        print(
            f"Average Time Spent Waiting in Queue (WQi): {avg_time_spent_waiting_in_queue}"
        )
        print(f"Utilization Rate: {utilization_rate}")

    def calculate_metrics(self, queues: Dict[str, Queue], simulation_time):
        WQi = {
            name: queue.total_delay / queue.num_serviced
            if queue.num_serviced > 0
            else 0
            for name, queue in queues.items()
        }
        Es = {
            name: sum(queue.service_times) / queue.num_serviced
            if queue.num_serviced > 0
            else 0
            for name, queue in queues.items()
        }
        Wi = {name: WQi[name] + Es[name] for name, _ in queues.items()}

        LQi = {
            name: queue.area_under_q / simulation_time for name, queue in queues.items()
        }
        rho = {
            name: queue.area_under_b / simulation_time for name, queue in queues.items()
        }

        Li = {name: LQi[name] + rho[name] for name, _ in queues.items()}

        return Li, LQi, Wi, WQi, rho


if __name__ == "__main__":
    random.seed(42)

    config = Config()

    s = Simulation(config)
    s.run()
