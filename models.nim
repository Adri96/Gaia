import options

type ObjectWithID = object of RootObj
            id: Option[int]

type Service = object of ObjectWithID
            name: string

type Need = object of ObjectWithID
            name: string

type ChemicalFormula = object of ObjectWithID
            name: string

type Energy = object
            energy: float

type Reaction = object of ObjectWithID
            input_1: ChemicalFormula
            input_2: ChemicalFormula
            output: ChemicalFormula
            energy: Energy # in J. If energy > 0, the reaction is endothermic; if energy < 0, exothermic

type ResourceKind = enum
            rkChemical, rkEnergy

type Resource = object
            case kind: ResourceKind
            of rkChemical:
                        formula: ChemicalFormula
            of rkEnergy:
                        energy: Energy

type NeedOfObject = object of ObjectWithID
            need: Need
            quantity: int

type ServiceOfObject = object of ObjectWithID
            service: Service
            quantity: int


type NaturalObject = object of ObjectWithID
            inputs: seq[Resource]
            outputs: seq[Resource]
            reactions: seq[Reaction]
            needs: seq[NeedOfObject]
            services: seq[ServiceOfObject]
            name: string

type ReactionInObject = object of ObjectWithID
            reaction: Reaction
            quantity: int

type LivingBeing = object of ObjectWithID


export Service, Need, ChemicalFormula, Reaction, NaturalObject,
    ReactionInObject, LivingBeing, Energy
