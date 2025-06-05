"""Backend optimization module for the app."""

import math
from random import randint

import numpy as np
from ortools.linear_solver import pywraplp


class SchedulingOptimizer:
    """Class to handle scheduling optimization using Kemeny-Young consensus ranking."""

    def __init__(self):  # noqa: D107
        self.slot_times = [
            [1, 's1', 'MWF 9:00-10:15', 'M/W/F', '9:00', '10:15'],
            [2, 's2', 'TT 9:00-10:15', 'T/TH', '9:00', '10:15'],
            [3, 's3', 'MWF 10:30-11:45', 'M/W/F', '10:30', '11:45'],
            [4, 's4', 'TT 10:30-11:45', 'T/TH', '10:30', '11:45'],
            [5, 's5', 'MWF 12:00-1:15', 'M/W/F', '12:00', '1:15'],
            [6, 's6', 'TT 12:00-1:15', 'T/TH', '12:00', '1:15'],
            [7, 's7', 'MWF 1:30-2:45', 'M/W/F', '1:30', '2:45'],
            [8, 's8', 'TT 1:30-2:45', 'T/TH', '1:30', '2:45'],
            [9, 's9', 'MWF 3:00-4:15', 'M/W/F', '3:00', '4:15'],
            [10, 's10', 'TT 3:00-4:15', 'T/TH', '3:00', '4:15'],
        ]

        self.slots = [i[1] for i in self.slot_times]
        self.mwf_set = [i[1] for i in self.slot_times if i[3] == 'M/W/F']
        self.tt_set = [i[1] for i in self.slot_times if i[3] == 'T/TH']
        self.mwf_slots = [i[0] - 1 for i in self.slot_times if i[3] == 'M/W/F']
        self.tt_slots = [i[0] - 1 for i in self.slot_times if i[3] == 'T/TH']
        self.fas_slot = [9]  # TT 3:00 pm slot

        # Start time slots
        self.t900 = [i[0] - 1 for i in self.slot_times if i[4] == '9:00']
        self.t1030 = [i[0] - 1 for i in self.slot_times if i[4] == '10:30']
        self.t1200 = [i[0] - 1 for i in self.slot_times if i[4] == '12:00']
        self.t130 = [i[0] - 1 for i in self.slot_times if i[4] == '1:30']
        self.t300 = [i[0] - 1 for i in self.slot_times if i[4] == '3:00']

    def rankaggr_lp(self, ranks):  # noqa: C901, PLR0912
        """Kemeny-Young consensus ranking using linear programming."""
        n_voters, n_candidates = ranks.shape

        if n_voters == 0 or n_candidates == 0:
            return float('inf'), np.zeros(n_candidates)

        solver = pywraplp.Solver('KemenyYoung', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

        x = {}
        for i in range(n_candidates):
            for j in range(n_candidates):
                if i != j:
                    x[i, j] = solver.BoolVar(f'x_{i}_{j}')

        obj_terms = []
        for voter in range(n_voters):
            for i in range(n_candidates):
                for j in range(n_candidates):
                    if i != j and ranks[voter, i] > 0 and ranks[voter, j] > 0:
                        if ranks[voter, i] < ranks[voter, j]:
                            obj_terms.append(x[j, i])
                        elif ranks[voter, i] > ranks[voter, j]:
                            obj_terms.append(x[i, j])

        if not obj_terms:
            return 0, np.ones(n_candidates)

        solver.Minimize(solver.Sum(obj_terms))

        # Transitivity constraints
        for i in range(n_candidates):
            for j in range(n_candidates):
                for k in range(n_candidates):
                    if j not in (i, k) and i != k:
                        solver.Add(x[i, j] + x[j, k] + x[k, i] <= 2)  # noqa: PLR2004

        status = solver.Solve()

        if status == pywraplp.Solver.OPTIMAL:
            consensus_scores = np.zeros(n_candidates)
            for i in range(n_candidates):
                for j in range(n_candidates):
                    if i != j and x[i, j].solution_value() > 0.5:  # noqa: PLR2004
                        consensus_scores[j] += 1
            return solver.Objective().Value(), consensus_scores

        # Fallback
        avg_ranks = np.zeros(n_candidates)
        for j in range(n_candidates):
            valid_prefs = ranks[:, j][ranks[:, j] > 0]
            if len(valid_prefs) > 0:
                avg_ranks[j] = np.mean(valid_prefs)
            else:
                avg_ranks[j] = 2.5
        return float('inf'), avg_ranks

    def get_slots_popularity(self, data):
        """Calculate slot popularity using Kemeny-Young consensus ranking."""
        ranks = data.values

        # Filter out rows with all zeros
        valid_ranks = ranks[~np.all(ranks == 0, axis=1)]

        if len(valid_ranks) == 0:
            # Fallback to equal popularity
            return dict.fromkeys(data.columns, 0.5), 0

        score, consensus_ranks = self.rankaggr_lp(valid_ranks.T)

        max_rank = np.max(consensus_ranks)
        min_rank = np.min(consensus_ranks)

        if max_rank == min_rank:
            slots_pop = dict.fromkeys(data.columns, 0.5)
        else:
            slots_pop = {}
            for i, slot in enumerate(data.columns):
                popularity = (max_rank - consensus_ranks[i]) / (max_rank - min_rank)
                slots_pop[slot] = popularity

        return slots_pop, score

    def get_satisfaction(self, slot, preference, slot_popularity):
        """Calculate satisfaction score for a course-slot assignment."""
        if preference == 0:
            return 0

        base_satisfaction = 5 - preference
        satisfaction = base_satisfaction - slot_popularity[slot]
        satisfaction += randint(1, 10) / 10

        return max(satisfaction, 0)

    def optimize_schedule(self, selection_data, course_data, faculty_data):  # noqa: C901, PLR0912
        """Run the optimization algorithm and return results."""
        num_courses = selection_data.shape[0]
        num_slots = selection_data.shape[1]
        num_stimes = 5

        # Get course labels
        course_labels = selection_data.index.tolist()

        # Get voting courses if faculty data provided
        voting_courses = []
        if faculty_data is not None and 'Voting' in faculty_data.columns:
            voting_faculty_names = faculty_data[faculty_data['Voting'] > 0].index.tolist()

            for course in course_labels:
                if course in course_data.index:
                    faculty_for_course = course_data.loc[course, 'Faculty']
                    if faculty_for_course in voting_faculty_names:
                        voting_courses.append(course_labels.index(course))

        # Calculate slot popularity
        slot_popularity, kemeny_score = self.get_slots_popularity(selection_data)

        # Build satisfaction matrix
        satisfaction_matrix = []
        for s in range(num_slots):
            slot = self.slots[s]
            old_row = selection_data[slot].tolist()
            new_row = []
            for i in range(num_courses):
                value = self.get_satisfaction(slot, old_row[i], slot_popularity)
                new_row.append(value)
            satisfaction_matrix.append(new_row)

        # Set up optimization
        solver = pywraplp.Solver('SolveMIP', pywraplp.Solver.CBC_MIXED_INTEGER_PROGRAMMING)

        set_min = math.ceil(num_courses / 2) - 1
        stime_min = int(num_courses / num_stimes)
        stime_max = stime_min + 2

        # Variables
        x = {}
        for i in range(num_slots):
            for j in range(num_courses):
                x[i, j] = solver.BoolVar(f'x[{i},{j}]')

        # Objective
        solver.Maximize(
            solver.Sum([satisfaction_matrix[i][j] * x[i, j] for i in range(num_slots) for j in range(num_courses)]),
        )

        # Constraints
        # Each course assigned to exactly one slot
        for j in range(num_courses):
            solver.Add(solver.Sum([x[i, j] for i in range(num_slots)]) == 1)

        # Balance MWF vs TT
        solver.Add(solver.Sum([x[i, j] for i in self.mwf_slots for j in range(num_courses)]) >= set_min)
        solver.Add(solver.Sum([x[i, j] for i in self.tt_slots for j in range(num_courses)]) >= set_min)

        # Balance start times
        for time_slots in [self.t900, self.t1030, self.t1200, self.t130, self.t300]:
            solver.Add(solver.Sum([x[i, j] for i in time_slots for j in range(num_courses)]) >= stime_min)
            solver.Add(solver.Sum([x[i, j] for i in time_slots for j in range(num_courses)]) <= stime_max)

        # FAS meeting constraint (if voting courses identified)
        if voting_courses:
            solver.Add(solver.Sum([x[i, j] for i in self.fas_slot for j in voting_courses]) == 0)

        # Solve
        status = solver.Solve()

        if status != pywraplp.Solver.OPTIMAL:
            return None, 'Optimization failed'

        # Extract results
        results = []
        output = np.zeros((num_courses, num_slots))

        for i in range(num_slots):
            for j in range(num_courses):
                if x[i, j].solution_value() > 0:
                    entry = {
                        'Course': course_labels[j],
                        'Slot': self.slot_times[i][1],
                        'Time': self.slot_times[i][2],
                        'Satisfaction': satisfaction_matrix[i][j],
                    }
                    results.append(entry)
                    output[j, i] = 1

        # Calculate summary statistics
        stats = self.calculate_stats(results, output, num_courses, num_slots)

        return {
            'results': results,
            'stats': stats,
            'output_matrix': output,
            'satisfaction_total': solver.Objective().Value(),
            'solve_time': solver.WallTime(),
            'slot_popularity': slot_popularity,
            'kemeny_score': kemeny_score,
        }, None

    def calculate_stats(self, results, output, num_courses, num_slots):  # noqa: ARG002
        """Calculate scheduling statistics."""
        mwf_count = sum(1 for r in results if r['Slot'] in self.mwf_set)
        tt_count = sum(1 for r in results if r['Slot'] in self.tt_set)

        # Count by start time
        time_counts = {
            '9:00': sum(1 for r in results if '9:00' in r['Time']),
            '10:30': sum(1 for r in results if '10:30' in r['Time']),
            '12:00': sum(1 for r in results if '12:00' in r['Time']),
            '1:30': sum(1 for r in results if '1:30' in r['Time']),
            '3:00': sum(1 for r in results if '3:00' in r['Time']),
        }

        # Count by slot
        slot_counts = output.sum(axis=0).tolist()

        return {
            'mwf_count': mwf_count,
            'tt_count': tt_count,
            'time_counts': time_counts,
            'slot_counts': slot_counts,
            'balance_diff': abs(mwf_count - tt_count),
            'time_diff': max(time_counts.values()) - min(time_counts.values()),
        }
