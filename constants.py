from enum import Enum, IntEnum


class Temperament(Enum):
    ALTRUISTIC = 1
    HOT_BLOODED = 2
    INTUITIVE = 3
    PARANOIAC = 4
    PATIENT = 5
    PREPARED = 6
    SCHOLASTIC = 7


class Condition(Enum):
    DEAD = 1
    INJURED = 2
    BUNKERING = 3
    ARMED = 4
    ARMORED = 5
    ARMED_SET = 6
    ARMOR_SET = 7
    GRIP = 8  # Can't be Disarmed
    SNIPING = 9
    AMBUSHED = 10
    GAS_IMMUNE = 11
    INFLICT_GRIEVOUS = 12
    GRIEVOUS = 13
    INFLICT_CAUTERIZE = 14
    CAUTERIZED = 15
    HEALER = 16  # Able to take the HEAL action
    PETRIFY = 17
    PETRIFIED = 18
    BONUS_HEALER = 19  # Able to take the HEAL action as a bonus action
    EFFICIENT_HEALER = 20  # Able to make full use of Medkits
    FORGED = 21  # Permanent Survivability increase
    AMBUSH_AWARE = 22
    SPY_AWARE = 23
    THEFT_AWARE = 24
    KNOW = 25  # Know Thy Enemy +1/+1 in combat
    PIERCE_COUNTER_INT = 26
    HOOK = 27
    THIEF = 28  # Can take the Steal Action
    COUNTER_INT = 29
    SUPER_COUNTER_INT = 30
    SABOTAGED_KNOWLEDGE = 31  # Counter Int 2 Know Thy Enemy -2/-2 to the other player
    HOOK_IGNORE = 32
    DEADLY_AMBUSH = 33  # Ambush Tactics 2
    CIRCUIT = 34
    FIRE_CIRCUIT = 35
    WATER_CIRCUIT = 36
    EARTH_CIRCUIT = 37
    AIR_CIRCUIT = 38
    LIGHT_CIRCUIT = 39
    ANTI_CIRCUIT = 40
    GEO_LOCKED = 41
    HYDRO_LOCKED = 42
    AERO_LOCKED = 43
    USING_GEO = 44
    USING_HYDRO = 45
    USING_AERO = 46
    FIRE_PROOF = 47
    FIRE_BODY = 48
    GRIEVOUS_IMMUNE = 49
    COMBAT_REGEN = 50
    MULTI_ATTACK = 51  # Can attack 3 players
    FRAGILE_BUNKERING = 52  # Special case that allows bunker bonuses to disappear with antimagic for earth 3
    BONUS_BUNKER = 53
    FRAGILE_BUNKER = 54  # Bonus bunker susceptible to antimagic
    LONG_PETRIFY = 55  # Petrify lasts an additional turn
    SNIPED = 56  # Used for Speed Calc
    RESURRECT = 57  # Return from Death
    STEALTH_REZ = 58  # Hide when returning from the dead
    HIDING = 59  # Don't show up in day reports
    FRESH_HIDING = 60  # Actions don't remove HIDING this turn
    NO_CONTINGENCY = 61  # Prevents Contingencies from happening
    HAS_WILLPOWER = 62  # Set if the player has any willpower to drain
    ILLUSIONIST = 63  # Can cast an illusion of actions
    DELUDED = 64  # -2 Combat from Illusion 2
    MASTER_ILLUSIONIST = 64  # Can cast illusion 3 target swap
    FRAGILE_ARMED = 65  # Armed that disappears from antimagic
    TARGET_LOCKED = 66  # Speed 0 and can't be immune to sniping
    AMBUSH_IMMUNE = 67
    UNNATURAL_INTUITION = 68  # Bonus vs Aero AND Reveals are Aero in range
    STUDIOUS = 69  # +1 Academics from Classes
    LOW_CRAFTING = 70  # Single item worth 2 or less
    CRAFTING = 71  # Combination of items adding up to less than 3
    HIGH_CRAFTING = 72  # Combination of items adding up to 5. No Liquid Memories


AFFLICTIONS = [Condition.DEAD, Condition.INJURED, Condition.GRIEVOUS, Condition.CAUTERIZED, Condition.PETRIFIED]


class InfoScope(Enum):
    HIDDEN = 0
    PUBLIC = 1
    PRIVATE = 2
    BROADCAST = 3
    PERSONAL = 4  # Like Private, but targets don't get to see, only the originator


class Effect(Enum):
    INFO = 0
    COMBAT = 1
    SURVIVABILITY = 2
    CONDITION = 3
    PERMANENT_CONDITION = 4
    WEAPON = 5
    DISARM = 6
    ARMOR = 7
    ARMOR_BREAK = 8
    SNIPING = 9
    NONLETHAL = 10
    NO_COMBAT = 11
    NO_SURVIVABILITY = 12
    AMBUSH = 13
    REL_CONDITION = 14
    DEV_SABOTAGE = 15  # Trade Secrets
    COPYCAT = 16
    TENTATIVE_CONDITION = 17  # Usually does not need to be set in the yaml
    BALANCE = 18  # Buff the smaller of Combat and Surv, prioritizing surv
    PROGRESS = 19
    REMOVE_CONDITION = 20
    INFO_ONCE = 21  # Info, but make sure not to duplicate
    SPEED = 22
    MAX_WILLPOWER = 23
    DRAIN = 24  # Drain Willpower
    INTUITION = 25  # Detect Aeromancy Concept


class Trigger(Enum):
    NONCOMBAT = 0  # Skill not used in combat
    SELF = 1
    ENEMY = 2  # EXPLICITLY Ignores Range
    ATTACK = 3
    RANGE = 4
    ATTACKED = 5
    RANGE_EX_SELF = 6
    COMBAT_INJURY = 10
    SPY = 11
    SPIED_ON = 12
    NONCOMBAT_POST_ATTUNE = 13  # Usually does not need to be set in the yaml
    POST_COMBAT = 14
    RANGE_IGNORE_SPEED = 15  # Used for speed affecting in range abilities to avoid edge cases
    TARGET = 16  # Manually selected target


NONCOMBAT_TRIGGERS = [Trigger.NONCOMBAT, Trigger.COMBAT_INJURY, Trigger.SPY, Trigger.SPIED_ON,
                      Trigger.NONCOMBAT_POST_ATTUNE, Trigger.POST_COMBAT, Trigger.TARGET]


class ItemType(Enum):
    CONSUMABLE = 1
    REACTIVE = 2
    WEAPON = 3
    ARMOR = 4
    PERMANENT = 5


class DamageType(IntEnum):
    DEFAULT = 1
    NONLETHAL = 2
    PETRIFY = 3


class InjuryModifier(IntEnum):
    NONLETHAL = 0
    GRIEVOUS = 1
    PERMANENT = 2


COMBAT_PLACEHOLDER = "%COMBAT%"
SELF_PLACEHOLDER = "%SELF%"
TARGET_PLACEHOLDER = "%TARGET%"


class Element(IntEnum):
    ANTI = 0
    FIRE = 1
    WATER = 2
    EARTH = 3
    AIR = 4
    LIGHT = 5
