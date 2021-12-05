from io import DEFAULT_BUFFER_SIZE
import random

# Params
simulations = 10000
show_combat_report = False

# Attacker stats
# Number of units
attacker_units = 20
# DEX/REF + combat stat
attacker_base = 12
# HP of each unit
attacker_hp = 25
# Armor of each unit
attacker_armor = 7
# Dice of damage that the main weapon does
attacker_dice = 4
# Tactics of the attacker squad leader
attacker_tactics = 10
# Condition of the attacker (values: ambush)
attacker_condition = None

# Defender stats
# Number of units
defender_units = 20
# DEX/REF + combat stat
defender_base = 12
# HP of each unit
defender_hp = 25
# Armor of each unit
defender_armor = 7
# Dice of damage that the main weapon does
defender_dice = 4
# Tactics of the attacker squad leader
defender_tactics = 10
# Condition of the attacker (values: hastydef/gooddef)
defender_condition = None


# Modifiers
ratio_mods = {
    "1-1": 0,
    "2-1": 1,
    "3-4": 2,
    "5+": 3,
}

troop_mods = {
    "2-9": -1,
    "10-13": 0,
    "14-16": 2,
    "17+": 4
}

condition_mods = {
    "ambush": 4,
    "gooddef": 2,
    "hastydef": 1
}


# Utils
def _quality(base_skill):
    if base_skill <=9:
        return "2-9"
    elif 9 < base_skill <= 13:
        return "10-13"
    elif 13 < base_skill <= 16:
        return "14-16"
    else:
        return "17+"

def roll_d6(num=1):
    return sum([random.randint(1,6) for i in range(num)])

def rolld10():
    dice = random.randint(1,10)
    if dice == 10:
        dice += random.randint(1,10)
    elif dice == 1:
        dice -= random.randint(1,10)
    return dice

def get_dmg_percentages(diff):
    abs_diff = abs(diff)
    if 0 <= abs_diff < 6:
        percentages = (0.5, 0.5)
    if 6 <= abs_diff < 10:
        percentages = (0.6, 0.4)
    elif 10 <= abs_diff < 15:
        percentages = (0.7, 0.3)
    else:
        percentages = (0.8, 0.2)
    
    if diff < 0:
        percentages = (percentages[1], percentages[0])
    return percentages

# Constants
class Winner(object):
    ATK = "attacker"
    DEF = "defender"


# Simulation Classes
class Unit(object):
    def __init__(self, base_skill, hp, armor, dice):
        self.base_skill = base_skill
        self.hp = hp
        self.armor = armor
        self.dice = dice
        self.quality = _quality(self.base_skill)

    def damage(self, damage):
        self.hp -= damage
        if self.hp <= 0:
            overflow = abs(self.hp)
            self.hp = 0 if self.hp < 0 else self.hp
            return overflow
        else:
            return 0

    def roll_attack(self):
        return roll_d6(self.dice)


class Forces(object):
    def __init__(self, units, leader_tactics, condition=None):
        self.units = units
        self.quality = _quality(sum([unit.base_skill for unit in self.units]) // len(self.units))
        self.armor_avg = sum([unit.armor for unit in self.units]) // len(self.units)
        self._last_ablated = -1
        self.leader_tactics = leader_tactics

        self.condition_mod = 0
        if (condition is not None):
            self.condition_mod = condition_mods[condition]
        self.quality_mod = troop_mods[self.quality]

        self.initial_hp = sum([unit.hp for unit in self.units])

    @property
    def armor(self):
        return sum([unit.armor for unit in self.units])

    def ablate_armor(self, number):
        for i in range(number):
            self._last_ablated += 1
            if (self._last_ablated >= len(self.units)):
                self._last_ablated = 0
            self.units[self._last_ablated].armor -= 1

    @property
    def alive_units(self):
        return [unit for unit in self.units if unit.hp > 0]

    def _next_alive(self):
        if self.alive_units:
            return self.alive_units[0]
        else:
            return None

    @property
    def hp(self):
        return sum([unit.hp for unit in self.units])

    def damage(self, damage):
        overflow = damage - self.armor
        while (overflow > 0):
            if not self._next_alive():
                return
            overflow = self._next_alive().damage(overflow)
        self.ablate_armor(damage // self.armor_avg)

    @property
    def losses(self):
        return (self.initial_hp - self.hp)/self.initial_hp

    @property
    def losses_mod(self):
        if self.losses <= 0.1:
            return 0
        elif 0.1 < self.losses <= 0.2:
            return -1
        elif 0.2 < self.losses <= 0.4:
            return -2
        else:
            return -4

    # Using only alive units model
    def roll_attack(self):
        return sum([unit.roll_attack() for unit in self.alive_units])


class CombatRound(object):
    def __init__(self, number, tactics, damage, actual_damage, multiplier, losses, hp, armor):
        self.number = number
        self.attacker_tactics, self.defender_tactics = tactics
        self.attacker_damage, self.defender_damage = damage
        self.attacker_actual_damage, self.defender_actual_damage = actual_damage
        self.attacker_multiplier, self.defender_multiplier = multiplier
        self.attacker_losses, self.defender_losses = losses
        self.attacker_hp, self.defender_hp = hp
        self.attacker_armor, self.defender_armor = armor

    def report(self):
        print(f"############### Round {self.number}")
        print(f"Atk Tactics: {self.attacker_tactics} / Def Tactics: {self.defender_tactics}")
        print(f"Atk damage: {self.attacker_damage} ({self.attacker_actual_damage} [{self.attacker_multiplier}])")
        print(f"Def damage: {self.defender_damage} ({self.defender_actual_damage} [{self.defender_multiplier}])")
        print(f"Atk hp: {self.attacker_hp} / Def hp: {self.defender_hp}")
        print(f"Atk losses: {self.attacker_losses} / Def losses: {self.defender_losses}")
        print(f"Atk armor: {self.attacker_armor} / Def armor: {self.defender_armor}")
        print("")

class SquadCombat(object):
    def __init__(self, attacker, defender, recalculate_ratio=False, report=False):
        self.attacker = attacker
        self.defender = defender
        self._recalculate_ratio = recalculate_ratio
        self._ratio_mod = self.get_ratio_mod()
        self.rounds = []
        self.winner = None
        self.report = report

    @property
    def ratio_mod(self):
        if self._recalculate_ratio:
            self._ratio_mod = self.get_ratio_mod()
        return self._ratio_mod

    def get_ratio_mod(self):
        atk_units = len(self.attacker.units)
        def_units = len(self.defender.units)
        ratio = atk_units/def_units if atk_units > def_units else def_units/atk_units
        if ratio < 1.5:
            ratio_mod = 0
        elif 1.5 <= ratio < 3:
            ratio_mod = 1
        elif 3 <= ratio < 5:
            ratio_mod = 2
        else:
            ratio_mod = 3

        if atk_units <= def_units:
            ratio_mod = -ratio_mod

        return ratio_mod

    def simulate_round(self, round_number):
        def get_roll(forces, ratio_mod=0):
            return rolld10() + forces.leader_tactics + forces.condition_mod + forces.quality_mod + forces.losses_mod + ratio_mod

        # Calculate tactics roll
        attacker_roll = get_roll(self.attacker, self.ratio_mod)
        defender_roll = get_roll(self.defender)
        tactics_diff = attacker_roll - defender_roll

        # Calculate attacks
        attacker_damage = self.attacker.roll_attack()
        defender_damage = self.defender.roll_attack()

        # Calculate percentages depending on the tactics rolls
        attacker_multiplier, defender_multiplier = get_dmg_percentages(tactics_diff)

        # Calculate actual damages
        attacker_actual_damage = int(attacker_damage * attacker_multiplier)
        defender_actual_damage = int(defender_damage * defender_multiplier)
        self.attacker.damage(defender_actual_damage)
        self.defender.damage(attacker_actual_damage)

        # Store the round
        self.rounds.append(CombatRound(
            round_number,
            (attacker_roll, defender_roll),
            (attacker_damage, defender_damage),
            (attacker_actual_damage, defender_actual_damage),
            (attacker_multiplier, defender_multiplier),
            (self.attacker.losses, self.defender.losses),
            (self.attacker.hp, self.defender.hp),
            (self.attacker.armor, self.defender.armor)
        ))

        if not self.attacker.alive_units:
            self.winner = Winner.DEF
        if not self.defender.alive_units:
            self.winner = Winner.ATK

        if self.report:
            self.rounds[-1].report()

    def simulate_battle(self):
        round_counter = 1
        while (self.winner is None):
            self.simulate_round(round_counter)
            round_counter += 1


# Simulate
combats = []
for simulation in range(simulations):
    if show_combat_report:
        print("#"*40)
        print(f"Combat simulation #{len(combats)+1}")
        print("#"*40)

    attacker = Forces([Unit(attacker_base, attacker_hp, attacker_armor, attacker_dice) for i in range(attacker_units)], attacker_tactics, condition=attacker_condition)
    defender = Forces([Unit(defender_base, defender_hp, defender_armor, defender_dice) for i in range(defender_units)], defender_tactics, condition=defender_condition)
    combat = SquadCombat(attacker, defender, report=show_combat_report)
    combat.simulate_battle()
    combats.append(combat)

avg_rounds = 0
avg_stats_per_round = {}
winner = {
    Winner.ATK: 0,
    Winner.DEF: 0,
}
for combat in combats:
    avg_rounds += len(combat.rounds)
    winner[combat.winner] += 1
    for round in combat.rounds:
        if round.number not in avg_stats_per_round:
            avg_stats_per_round[round.number] = {
                "count": 0,
                "atk_avg_roll": 0,
                "def_avg_roll": 0,
                "atk_avg_dmg": 0,
                "def_avg_dmg": 0,
                "atk_avg_losses": 0,
                "def_avg_losses": 0,
                "atk_avg_hp": 0,
                "def_avg_hp": 0,
                "atk_avg_armor": 0,
                "def_avg_armor": 0,
            }
        avg_stats_per_round[round.number]["count"] += 1
        avg_stats_per_round[round.number]["atk_avg_roll"] += round.attacker_tactics
        avg_stats_per_round[round.number]["def_avg_roll"] += round.defender_tactics
        avg_stats_per_round[round.number]["atk_avg_dmg"] += round.attacker_actual_damage
        avg_stats_per_round[round.number]["def_avg_dmg"] += round.defender_actual_damage
        avg_stats_per_round[round.number]["atk_avg_losses"] += round.attacker_losses
        avg_stats_per_round[round.number]["def_avg_losses"] += round.defender_losses
        avg_stats_per_round[round.number]["atk_avg_hp"] += round.attacker_hp
        avg_stats_per_round[round.number]["def_avg_hp"] += round.defender_hp
        avg_stats_per_round[round.number]["atk_avg_armor"] += round.attacker_armor
        avg_stats_per_round[round.number]["atk_avg_armor"] += round.attacker_armor

for round in avg_stats_per_round.keys():
    avg_stats_per_round[round]["atk_avg_roll"] = avg_stats_per_round[round]["atk_avg_roll"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["def_avg_roll"] = avg_stats_per_round[round]["def_avg_roll"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["atk_avg_dmg"] = avg_stats_per_round[round]["atk_avg_dmg"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["def_avg_dmg"] = avg_stats_per_round[round]["def_avg_dmg"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["atk_avg_losses"] = avg_stats_per_round[round]["atk_avg_losses"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["def_avg_losses"] = avg_stats_per_round[round]["def_avg_losses"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["atk_avg_hp"] = avg_stats_per_round[round]["atk_avg_hp"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["def_avg_hp"] = avg_stats_per_round[round]["def_avg_hp"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["atk_avg_armor"] = avg_stats_per_round[round]["atk_avg_armor"] / avg_stats_per_round[round]["count"]
    avg_stats_per_round[round]["atk_avg_armor"] = avg_stats_per_round[round]["atk_avg_armor"] / avg_stats_per_round[round]["count"]
avg_rounds = avg_rounds/simulations

print("#" * 40)
print("# Averages per round")
print("#" * 40)
for round in avg_stats_per_round.keys():
    print(f"Round {round}")
    print(f'Number of combats reached this round: {avg_stats_per_round[round]["count"]}')
    print(f'Average attacker roll: {avg_stats_per_round[round]["atk_avg_roll"]}')
    print(f'Average defender roll: {avg_stats_per_round[round]["def_avg_roll"]}')
    print(f'Average attacker damage: {avg_stats_per_round[round]["atk_avg_dmg"]}')
    print(f'Average defender damage: {avg_stats_per_round[round]["def_avg_dmg"]}')
    print(f'Average attacker losses: {avg_stats_per_round[round]["atk_avg_losses"]}')
    print(f'Average defender losses: {avg_stats_per_round[round]["def_avg_losses"]}')
    print(f'Average attacker hp: {avg_stats_per_round[round]["atk_avg_hp"]}')
    print(f'Average defender hp: {avg_stats_per_round[round]["def_avg_hp"]}')
    print(f'Average attacker armor: {avg_stats_per_round[round]["atk_avg_armor"]}')
    print(f'Average defender armor: {avg_stats_per_round[round]["def_avg_armor"]}')
    print("")

print("")
print(f"Average number of rounds: {avg_rounds}")
print(f"Number of attacker victories: {winner[Winner.ATK]}")
print(f"Number of defender victories: {winner[Winner.DEF]}")