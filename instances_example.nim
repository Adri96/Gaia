from models import NaturalObject, Reaction, Energy

let ENERGY* = Energy(
  energy: 1.361 # in J/(s·m²), mean solar constant at Earth's distance
)

let SUN* = NaturalObject(
  inputs: @[],
  outputs: @[ENERGY],
  reactions: @[ENERGY],
  needs: @[],
  services: @[],
  name: "Sun"
)


