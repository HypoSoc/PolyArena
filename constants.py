from enum import Enum, IntEnum


class Temperament(IntEnum):
    NONE = 0
    ALTRUISTIC = 1
    HOT_BLOODED = 2
    INTUITIVE = 3
    PARANOIAC = 4
    PATIENT = 5
    PREPARED = 6  # No longer used
    SCHOLASTIC = 7
    LUCRATIVE = 8
    PRIVILEGED = 9
    INNOVATIVE = 10
    BLOODTHIRSTY = 11


class Condition(IntEnum):
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
    # Special case that allows bunker bonuses to disappear with antimagic for earth 3
    FRAGILE_BUNKERING = 52
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
    UNNATURAL_INTUITION = 68  # Bonus vs Aero AND Reveals any Aero in range
    STUDIOUS = 69  # +1 Academics from Classes
    LOW_CRAFTING = 70  # Single item worth 2 or less
    CRAFTING = 71  # Combination of items adding up to less than 3
    HIGH_CRAFTING = 72  # Combination of items adding up to 5. No Liquid Memories
    INTUITION = 73  # Aeromancy Intuition
    IMPOSING = 74  # Reality Imposition
    AEROMANCER = 75  # Permanently marks Aeromancers
    ONCE = 76  # Marker for once
    CHARGE = 77  # Marker for charges
    OPTION_A = 78
    OPTION_B = 79
    OPTION_C = 80
    OPTION_D = 81
    OPTION_E = 82
    OPTION_F = 83
    OPTION_G = 84
    OPTION_H = 85
    OPTION_I = 86
    OPTION_J = 87
    SCHOOLED = 88  # Went to Class
    TRAINED = 89  # Trained
    SHOPPED = 90  # Shopped
    DOCTOR = 91  # Went to the Doctor
    ATTACKED = 92  # Attacked
    WANDERED = 93  # Wandered
    LOCKED = 94
    MARKED = 95
    CRUMBLING = 96  # -1 Survivability when petrified
    RINGER = 97  # Is the ringer
    SICKENED = 98
    SICK_IMMUNE = 99
    COMBAT_DOWN = 100  # -1 Combat
    SURVIVABILITY_DOWN = 101  # -1 Survivability
    ORDERLY = 102
    HONED = 103  # Permanent Combat Increase
    DAY_SPY = 104
    CAN_SPY = 105
    ECLIPSE = 106
    PORTENT = 107
    OMEN = 108
    CELEBRATED = 109
    NONLETHAL_IMMUNE = 110  # Ignore damage with the Nonlethal modifier
    RINGING = 111
    SLIMED = 112
    POLLUTED = 113
    SANITARY = 114
    NO_SHOP = 115
    NO_CLASS = 116
    NO_PROGRESS = 117
    NO_COMBAT = 118
    WARP_CIRCUIT = 119
    USING_WARP = 120
    DEPLETED_CHARGE = 121  # For counting charges
    ONCE_AGAIN = 122  # For when a single ONCE isn't sufficient.
    BALANCE = 123  # the status equivalent of the balance skills, only acts during the combat phase
    # the status equivalent of the imbalance skills, only acts during the combat phase
    IMBALANCE = 124
    INCREASED_SPEED = 125
    SUPPRESSED = 126
    SPY_IMMUNE = 127
    CURSED = 128
    CURSE_IMMUNE = 129
    CRUMBLING_IMMUNE = 130
    NIGHT_LIGHT = 131
    PIERCE_ILLUSIONS = 132
    BLACKMAILING = 133
    NO_PROGRESS_NEXT_TURN = 134
    BREWING = 135  # To make Toxin work with Fast Attune
    SABOTAGE = 136  # Immune to Sabotage
    TAUNT = 137
    TAUNT_IGNORE = 138
    GOLD_CIRCUIT = 139
    DECOY_ATTACKED = 140
    ATTEMPT_CLASS = 141
    ATTEMPT_SHOP = 142
    ATTEMPT_DOCTOR = 143


AFFLICTIONS = [Condition.DEAD, Condition.INJURED, Condition.GRIEVOUS, Condition.CAUTERIZED, Condition.PETRIFIED,
               Condition.PORTENT, Condition.CURSED, Condition.NO_PROGRESS_NEXT_TURN]

NEGATIVE_CONDITIONS = [Condition.DEAD, Condition.INJURED, Condition.GRIEVOUS, Condition.CAUTERIZED, Condition.PETRIFIED,
                       Condition.PORTENT, Condition.CURSED, Condition.NO_PROGRESS_NEXT_TURN, Condition.SICKENED,
                       Condition.POLLUTED, Condition.CRUMBLING, Condition.SURVIVABILITY_DOWN, Condition.COMBAT_DOWN,
                       Condition.MARKED, Condition.SLIMED, Condition.SUPPRESSED, Condition.LOCKED]

CONDITION_IMMUNITY = {
    Condition.SICKENED: Condition.SICK_IMMUNE,
    Condition.POLLUTED: Condition.SANITARY,
    Condition.CURSED: Condition.CURSE_IMMUNE,
    Condition.CRUMBLING: Condition.CRUMBLING_IMMUNE
}


class InfoScope(Enum):
    HIDDEN = 0
    PUBLIC = 1
    PRIVATE = 2
    BROADCAST = 3
    PERSONAL = 4  # Like Private, but targets don't get to see, only the originator
    IMPERSONAL = 5  # Like Private, but ONLY the targets see, not the originator
    WIDE = 6  # Like Public, but for Aero. Players with AI will learn concept names but not aeromancer names
    NARROW = 7  # Like Private, but for Aero. Players with AI will learn concept names and aeromancer name
    SUBTLE = 8  # Like Narrow, but AI is necessary to SEE the message
    BLATANT = 9  # Like Broadcast, but for Aero. Players with AI will learn concept names but not aeromancer names
    # Like Broadcast, but also reveals the aeromancer name and concept to EVERYONE, no AI needed
    UNMISTAKABLE = 10
    SUBTLE_IMPERSONAL = 11  # Subtle, but the aeromancer does not get to see it
    NARROW_IMPERSONAL = 12  # Narrow, but the aeromancer does not get to see it


class Effect(Enum):
    INFO = 0
    COMBAT = 1
    SURVIVABILITY = 2
    CONDITION = 3
    TURN_CONDITION = 3.5
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
    REMOVE_REL_CONDITION = 14.5
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
    PETRIFY = 26
    ITEM = 27  # Gain Item
    CREDITS = 28  # Gain or Lose Credits
    DAMAGE = 29  # Directly damage a foe
    INTERRUPT = 30  # Prevent interruptable actions
    SCHEDULE = 31  # Schedule skill value in value_b turns
    # Grant the ability, or grant equivalent progress if ability cannot be gained
    GAIN_ABILITY_OR_PROGRESS = 32
    GRIEVOUS = 33  # Deal grievous damage
    MINI_PETRIFY = 34  # Petrify for this turn only
    KILL = 35  # Instantly kill (unless lizard tail)
    ACADEMIC = 36  # Gain academic points
    HEAL = 37
    IMBALANCE = 38  # Buff the larger of Combat and Surv, prioritizing combat
    CONSUME = 39  # turns a condition into a list of conditions.
    TEMP_SKILL = 40  # Grant a skill for a turn
    DUST = 41  # Destroy consumables and reactives


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
    # Used for speed affecting in range abilities to avoid edge cases
    RANGE_IGNORE_SPEED = 15
    TARGET = 16  # Manually selected target
    ACQUISITION = 17
    START_OF_GAME = 18  # Only happens at start of Game
    ALL = 19  # Affects all players outside combat
    OTHERS = 20  # Affects all players but the user
    ATTACKED_IGNORE_RANGE = 21
    COMBAT_DAMAGED = 22  # Triggers when damaged targeting the source
    RANDOM = 23  # Random Player
    RANDOM_OTHER = 24
    PLAYER_DIED = 25  # Happens whenever a player dies. Target is the dead player


NONCOMBAT_TRIGGERS = [Trigger.NONCOMBAT, Trigger.COMBAT_INJURY, Trigger.SPY, Trigger.SPIED_ON,
                      Trigger.NONCOMBAT_POST_ATTUNE, Trigger.POST_COMBAT, Trigger.TARGET,
                      Trigger.ACQUISITION, Trigger.START_OF_GAME, Trigger.ALL, Trigger.OTHERS,
                      Trigger.RANDOM, Trigger.RANDOM_OTHER,
                      Trigger.PLAYER_DIED]


class ItemType(Enum):
    CONSUMABLE = 1
    REACTIVE = 2
    WEAPON = 3
    ARMOR = 4
    PERMANENT = 5
    AUTOMATA = 6


class DamageType(IntEnum):
    DEFAULT = 1
    NONLETHAL = 2
    PETRIFY = 3


class InjuryModifier(IntEnum):
    NONLETHAL = 0
    GRIEVOUS = 1
    PERMANENT = 2
    MINI = 3  # Used by petrify only


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
    WARP = 6
    GOLD = 7
