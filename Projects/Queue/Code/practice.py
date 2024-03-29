from typing import Dict, List
import simpy
import random
from tabulate import tabulate


class Config:
    def __init__(self):
        self.inter_arrival_rate = 1.0
        self.mu_1 = 2.0
        self.mu_2 = 4.0
        self.mu_3 = 3.0
        self.simulation_time = 1000


class Queue:
    def __init__(self, env, mu, id):
        self.env = env
        self.mu = mu
        self.id = id
        self.server = simpy.Resource(env, capacity=1)
        self.num_serviced = 0
        self.num_in_queue = 0
        self.total_delay = 0
        self.times_of_arrival = []
        self.times_of_arrival_debug = []
        self.service_times = []
        # self.service_times_static = [2.0, 0.7, 0.2, 1.1, 3.7, 0.6]
        self.area_under_b = 0  # sum active time
        self.area_under_q = 0  # sum in queue by time
        self.last_event_time = 0
        self.server_status = 0

    def process(self):
        self.times_of_arrival.append(self.env.now)
        self.times_of_arrival_debug.append(self.env.now)

        self.update_stats()
        self.num_in_queue += 1
        # self.print_stats()

        with self.server.request() as request:
            yield request
            self.server_status = 1

            # if len(self.service_times_static) == 0:
            #     return
            # print(self.service_times_static)
            # service_time = self.service_times_static.pop(0)

            self.total_delay += self.env.now - self.times_of_arrival.pop(0)
            self.num_in_queue -= 1
            self.num_serviced += 1
            self.update_stats()
            # self.print_stats()

            service_time = random.expovariate(self.mu)
            yield self.env.timeout(service_time)
            self.service_times.append(service_time)

            self.update_stats()
            if self.num_in_queue == 0:
                self.server_status = 0

            # self.print_stats()

    def update_stats(self):
        time_since_last_event = self.env.now - self.last_event_time
        self.last_event_time = self.env.now

        self.area_under_b += time_since_last_event * self.server_status
        self.area_under_q += time_since_last_event * self.num_in_queue

    def print_stats(self):
        print("time", self.env.now)
        print("num_serviced", self.num_serviced)
        print("num_in_queue", self.num_in_queue)
        print("total_delay", self.total_delay)
        print("times_of_arrival", self.times_of_arrival)
        print("service_times", self.service_times)
        print("area_under_b", self.area_under_b)
        print("area_under_q", self.area_under_q)
        print("last_event_time", self.last_event_time)
        print("server_status", self.server_status)
        print("")


class Customer:
    def __init__(
        self, env: simpy.Environment, queues: Dict[str, Queue], config: Config
    ):
        self.env = env
        self.queues = queues
        self.config = config
        self.inter_arrival_times = []
        # self.inter_arrival_times_static = [0.4, 1.2, 0.5, 1.7, 0.2, 1.6, 0.2, 1.4, 1.9]

    def process(self):
        while True:
            # while len(self.inter_arrival_times_static) > 0:
            inter_arrival_time = random.expovariate(self.config.inter_arrival_rate)
            # inter_arrival_time = self.inter_arrival_times_static.pop(0)
            self.inter_arrival_times.append(inter_arrival_time)

            yield self.env.timeout(inter_arrival_time)

            self.env.process(self.process_customer())

    def process_customer(self):
        queue = self.queues["1"]
        yield self.env.process(queue.process())

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
            "1": Queue(self.env, config.mu_1, 1),
            "2": Queue(self.env, config.mu_2, 2),
            "3": Queue(self.env, config.mu_3, 3),
        }

    def run(self):
        c = Customer(self.env, self.queues, self.config)
        self.env.process(c.process())
        self.env.run(until=self.config.simulation_time)

        # print("inter arrival times\t", [round(i, 2) for i in c.inter_arrival_times])
        # print(
        #     "times_of_arrival q1\t",
        #     [round(i, 2) for i in self.queues["1"].times_of_arrival_debug],
        # )
        # print(
        #     "service_times q1\t", [round(i, 2) for i in self.queues["1"].service_times]
        # )
        # print(
        #     "times_of_arrival q2\t",
        #     [round(i, 2) for i in self.queues["2"].times_of_arrival_debug],
        # )
        # print(
        #     "service_times q2\t", [round(i, 2) for i in self.queues["2"].service_times]
        # )
        # print(
        #     "times_of_arrival q3\t",
        #     [round(i, 2) for i in self.queues["3"].times_of_arrival_debug],
        # )
        # print(
        #     "service_times q3\t", [round(i, 2) for i in self.queues["3"].service_times]
        # )

        (
            avg_num_waiting_customers,
            avg_num_customers,
            avg_waiting_time,
            avg_spent_time,
            utilization_rate,
        ) = self.calculate_metrics(self.queues, self.config.simulation_time)

        headers = ["Queue 1", "Queue 2", "Queue 3"]

        data = [
            (
                "Average number of waiting customers (LQ_i)",
                *avg_num_waiting_customers.values(),
            ),
            (
                "Average number of customers in system (L_i)",
                *avg_num_customers.values(),
            ),
            ("Average customer waiting time (WQ_i)", *avg_waiting_time.values()),
            ("Average customer time spent in system (W_i)", *avg_spent_time.values()),
            ("Average server utilization", *utilization_rate.values()),
        ]

        print(tabulate(data, headers=headers, tablefmt="grid"))

        print("Average number of customers in network (N):", sum(avg_num_customers.values()))
        print("Average network response time for all customers (R):", sum(avg_num_customers.values()) / self.config.inter_arrival_rate)

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

        return LQi, Li, WQi, Wi, rho


if __name__ == "__main__":
    random.seed(42)

    config = Config()

    s = Simulation(config)
    s.run()
