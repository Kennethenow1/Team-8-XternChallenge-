---
doc_id: bpm-015-r32-clean
section_id: app_H
section_title: Appendix H
start_page: 154
end_page: 161
status: superseded
source_pdf: 03_bpm-015-r32_generator_interconnection_clean.pdf
---

# app_H Appendix H

Appendix H
Grid-Forming Battery Energy Storage System Conformity Assessment Procedures

General
The simulation tests described below are MISO’s proposed method of demonstrating conformity
with MISO’s GFM BESS capability and performance requirements. MISO business practices
may change as control technologies, industry practices, and standards evolve. Table H.1
summarizes the purpose for each of the four tests.

Test
Purpose
Loss of Last Synchronous
Machine (LLSM)
Assess general grid-forming capabilities and performance following
the loss of the last synchronous generator on the test system given
various initial BESS dispatch conditions, including charging and
discharging
Rate of Change of
Frequency (ROCOF)
Assess control stability and active power responses for increases
and decreases in frequency
Phase Jump
Assess active power responses for voltage phase angle changes
Short Circuit Ratio (SCR)  Assess control stability in weak grid conditions before and after
faults are applied
Table H.1. Summary of the four conformance tests and each test’s purpose

While the tests are expected to definitively determine GFM BESS capability, they are not
intended to validate control stability performance under all potential grid conditions. Since the
stability of control responses can in part be dependent on electrical system characteristics (e.g.,
weak grid) and interactions with other system components, the tests have substantial but not full
coverage in evaluating GFM BESS control performance under a reasonable set of system
conditions. In addition, the tests contain extreme conditions not anticipated on the grid for the
purpose of exercising and understanding GFM BESS responses.

As is the case for all bulk system resources, interconnection studies are still required to evaluate
steady state and dynamic impacts of the GFM BESS plant for the selected point of
interconnection, given the system characteristics and conditions in that area.
MISO is not proposing additional interconnection study EMT simulations as part of the GFM
requirements proposal.

Functional test systems
Two functional test set-ups within PSCAD are needed to demonstrate stable grid forming control
responses across a range of simulated system disturbances. Table H.2 shows the application of
the test set-ups across the required simulations.

Test set-up
Simulations
A – Loss of last Synchronous
Machine
1. Loss of last synchronous machine
(Cases 1 – 3)
B – Variable source and
impedance
2. Rate of change of frequency
3. Phase jump
4. Low SCR with fault
Table H.2. Summary of test set-up mapping to simulations

The GFM BESS shall be in voltage control mode with identical voltage and frequency control
settings and set points.

The GFM BESS voltage and frequency protection settings shall be set as wide as possible
within equipment capabilities and ratings (i.e., self-protection). These settings shall be
consistent with the intended field application.

Test set-up A: Loss of last synchronous machine
Test set-up A (loss of last synchronous machine) is from NERC’s 2023 guideline. It is a
simplified power system consisting of a synchronous machine, constant impedance load, and
two GFM BESS (Figure H.1).

Figure H.1. Test set-up A configured for 100 MW GFM BESS (source: NERC)

The synchronous generator is approximated by using a simple voltage source rather than a
synchronous generator model. The test results are unaffected by representing the synchronous
generator as a simple voltage source because GFM BESS dynamic responses occurs only after
the generator or source is disconnected, leaving no potential for interaction between simulated
GFM dynamic response and these other modeled components.

The set-up includes the GFM BESS plant under test and a duplicate, half-rated GFM BESS
plant. The fully rated GFM BESS is the plant under test while the half-rated duplicate is used to
demonstrate compatibility among GFM controls, as well as to allow the fully rated GFM BESS to
be dispatched at its limit during testing. The half-rated unit could be represented by a separate
model or by scaling the original model.

Test set-up B: Variable source and impedance
Test set-up B (variable source and impedance) consists of an ideal, controllable voltage source
connected to the GFM BESS through a controllable impedance (Figure H.2). Additionally, a
variable impedance fault component is required for one of the three tests that uses this test set-
up, the low SCR with fault test.
The voltage source magnitude, phase, and frequency shall be user configurable. Similarly, the
series impedance shall be configurable such that the simulated GFM BESS connection point
strength (i.e., impedance and X/R ratio) and voltage is configurable.

Figure H.2. Test set-up B: variable source and impedance (source: AEMO)


Test descriptions and success criteria

Loss of last synchronous machine test
The loss of last synchronous machine (LLSM) test consists of three cases on test set-up A,
using different pre-disturbance conditions to test different aspects of the GFM BESS control
response. Table H.3 summarizes the conditions for each case, with detailed descriptions of the
test sequences and success criteria below the table.

Case  Description Project
Plant1
Duplicate
Plant1
Load2

(% of
project
plant
rating)
1
BESS
Charging
50%
charge
50%
charge
50%
2
Limit Test  0%
exchange
100%
discharge
100%
3
Power
Balance
50%
discharge
50%
discharge
75%
Notes: (1) values are as a percentage of the IBR continuous active power rating. (2) load
values are expressed as a percentage of the project plant active power continuous
rating.
Table H.3. Summary of cases associated with loss of last synchronous machine
simulations

In all three cases, the synchronous machine is supplying all the load’s reactive power prior to
the simulated disturbance (i.e., opening of breaker). The load is configured with a power factor
of 0.95 lagging in each case.

LLSM test sequence
The following test sequence is consistent across all three loss of last synchronous machine
cases:
1. Initiate simulation and run until system is stable at the given power flow conditions,
without oscillations.41
2. Trip the synchronous generator by opening the breaker (no fault).

LLSM success criteria
The following success criteria are consistent across all three cases, with minor clarifications
made for case 3 in footnotes.42  Refer to Table for required initial conditions of resources and
load prior to the synchronous generator tripping. All pre-trip and post-trip conditions shall be met
for the test to be considered “pass”.

Pre-trip:
a. Both BESS plants active power outputs match dispatched levels.

b. Synchronous generator active power output matches the rest of the load.
c. Frequency is 1 p.u.
d. Voltage at bus 1 is within 5% of nominal (i.e., 0.95 to 1.05 p.u.).
e. Phase voltage and current waveforms are not distorted.
f. Oscillations are not present in RMS quantities.
g. Reactive power output from all devices should be within limits.

The synchronous generator breaker is opened after pre-trip conditions are met.

Post-trip:
a. Plant output is well controlled with no significant frequency/voltage oscillations.
b. Voltage settles to a stable operating point.
c. Final voltage is expected based on droop and deadband settings.
d. Frequency settles to a stable operating point.43
e. Final frequency is expected based on droop and deadband settings.
f. Oscillations is adequately damped.
g. Distortion observed in phase quantities dissipates over time.
h. Active power immediately moves to meet load requirement and settle according to its
frequency droop setting. 44
i.
Reactive power response is immediate and settles according to voltage droop setting.45
a. Voltage should not deviate beyond 0.8 pu or 1.1 pu for longer than 0.1s throughout the
test.

Rate of change of frequency response test
The rate of change of frequency test (ROCOF) tests the stability of GFM BESS in response to
changing frequency. The test procedure includes both frequency increases and
decreases.  Test set-up B is used for the ROCOF test, with the following conditions:
•
The short circuit ratio (SCR) at the GFM BESS connection point shall be set to 10.
•
The system equivalent X/R shall be set to 6.
•
The BESS is dispatched to 50% of continuous rating.

ROCOF test sequence
1. Ramp frequency from 60 to 61 Hz at 4 Hz/s.  Remain at 61 Hz for 5 seconds.
2. Ramp frequency from 61 to 60 Hz at 4 Hz/s.  Remain at 60 Hz for 5 seconds.
3. Ramp frequency from 60 to 59 Hz at 4 Hz/s.  Remain at 59 Hz for 5 seconds.

4. Ramp frequency from 59 to 60 Hz at 4 Hz/s.

ROCOF success criteria
a. Plant output is well controlled with no significant frequency/voltage oscillations.46
b. Voltage settles to stable operating point when frequency is not ramping.
c. Active power should settle based on frequency droop and deadband settings when
frequency is not ramping.
d. Oscillations should be adequately damped.

Phase Jump test
The phase jump test evaluates the speed and magnitude of simulated active power responses
under different phase angle changes. Test set-up B is used for the phase jump test, with the
following conditions:
•
The short circuit ratio (SCR) at the GFM BESS connection point shall be set to 3
•
The system equivalent X/R shall be set to 6.
•
The BESS is dispatched to 50% of continuous rating.

Phase jump test sequence
a. Angle of voltage source behind the equivalent grid impedance is decreased
instantaneously by 10 degrees.
b. Five seconds47 later, angle of voltage source is increased by 10 degrees.
c. Angle of voltage source behind the equivalent grid impedance is decreased
instantaneously by 25 degrees.
d. Five seconds later, angle of voltage source is increased by 25 degrees.

Phase jump success criteria
a. Instantaneous active power output of the plant should quickly respond to oppose the
angle change for each of the 10 degree voltage phase angle jumps, with a peak active
power change of at least 0.2 pu on the rated active power base.
Example: 100 MW rated plant should temporarily increase active power output from 50 MW to
at least 70 MW when source voltage angle is decreased by 10 degrees, and should temporarily
decrease active power from 50 to 30 MW or below when voltage source angle is increased by
10 degrees.
b. For each of the 10 degree voltage phase angle jumps, response time to 90% of initial
change in instantaneous active power should occur within 15ms48.

c. Active power settles to pre-disturbance level shortly after all phase jumps.
d. Any oscillation shall be settled.
e. Any distortion observed in phase quantities should dissipate over time.

Short Circuit Ratio (SCR) ramp down with fault test
The SCR ramp down with fault test evaluates GFM BESS control stability under declining
system strength conditions (i.e., weak grid). The test starts with higher SCR values before
introducing a fault and stepping down SCR while simultaneously clearing the fault. This
sequence is repeated several times until very weak grid conditions are simulated. Test set-up B
is used with the following conditions:
•
The short circuit ratio (SCR) at the GFM BESS connection point shall be set to 20.
•
The system equivalent X/R shall be set to 6.
•
The BESS is dispatched to 100% of continuous rating.

SCR ramp down with fault test sequence
a. SCR at connection point stepped down repeatedly: 10, 3, 2, 1.5, 1.25.
b. 6-cycle 2 phase-to-ground fault is applied with minimum fault depth of 0.5pu just before
each SCR transition.  SCR transition occurs at fault clearing time.49

SCR ramp down with fault success criteria
Plant real and reactive power output should be well controlled and plant should not trip or
reduce power for any extended period of time down to the minimum SCR in the test
