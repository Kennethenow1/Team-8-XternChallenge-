---
doc_id: bpm-015-r33-redlines
section_id: app_I
section_title: Appendix I
start_page: 166
end_page: 203
status: redlines
source_pdf: 02_bpm-015-r33_generator_interconnection_redlines.pdf
---

# app_I Appendix I

Appendix I
Inverter-Based Resource (IBR) Modeling Requirements
I-1 Scope and Applicability
Midcontinent Independent System Operator (MISO) requires submission of the following
four simulation models for all inverter-based resources (IBRs) connecting to the MISO
system to comply with FERC Order 2023 [1][1] and North American Electric Reliability
Corporation (NERC) Reliability Standards [2][2]:
1. Standard library (“generic”) dynamic models (used in both PSS®E and TSAT™)
2. PSS®E user-written (aka, user-defined) models (PSS®E UDM)
3. TSAT™ user-defined models (TSAT™ UDM)
4. PSCAD™ models
This document describes the model requirements, model quality checks, simulation test
procedures, and pass/fail criteria of testing these models. These model requirements
are applicable to all IBRs, including solar photovoltaic (PV), battery energy storage
system (BESS), type III and IV wind plants, as well as co-located and hybrid plants
comprised of combinations of these resource types (e.g., solar PV plus BESS or wind
plus BESS).39 The requirements in this document are specific to models used to
analyze fault ride-through capability, fault ride-through performance, and converter-
driven stability [4][4]. Other specialized analyses may necessitate additional model
features.40
To fulfill the model submittal requirements, an interconnection customer shall submit the
following:
• The four required types of site-specific models (i.e., PSS®E standard library
model, PSS®E UDM, TSAT™ UDM, and PSCAD™ model) including all required
files and documentations that comply with model requirements listed in Section
04.
• One test report summarizing results of model quality and performance tests listed
in Model Quality and Test Report section, including benchmarking between
model types.



39 This excludes standalone high-voltage direct current (HVDC) systems. HVDC systems that are deployed for the sole purpose of interconnecting an IBR
plant are included.
40 For example, analysis of harmonics.

Understanding MISO IBR performance requirements [3][3] and IEEE 2800-2022 [5][5] is
essential for the application of this document. The requirements listed in this document
shall be met prior to the interconnection.
These requirements are applicable for all interconnection projects starting in the DPP
2025 cycle. DPP 2025 interconnection requests shall submit materials by kick-off of
Phase 2 instead of at the interconnection request. All subsequent cycles shall follow the
Model Submittal Process Flow in Section 2.
Surplus and Replacement submissions shall meet these requirements once DPP 2025
Phase 3 models are initially posted.

These requirements are not retroactively applicable to projects prior to the DPP 2025
cycle.
I-2 Model Submittal Process Flow
Figure 5Figure 1 depicts modeling milestones that shall be met as a prerequisite to
entering each phase of the process. Each milestone includes the models that shall be
submitted, required updates to the models (if applicable), and the model quality and
performance test report . Changes to a model shall require a new submission of the
modeling package and an accompanying model quality and performance test report.
Key milestones include:

• Interconnection Request: The interconnection customer shall submit a dynamic
model package that includes three model types (PSS®E standard library model,
TSATTM UDM, and PSCADTM). All models shall meet applicable modeling
requirements as defined in Section 04. The models shall be accompanied by a
model quality and performance test report as defined in Sections 04 and 5, that
adequately demonstrates the models and proposed IBR plant meet the
necessary quality and performance requirements. DPP 2025 interconnection
requests shall submit these materials by Phase 2 kick off.
• Definitive Planning Process Decision Points 1 and 2: The interconnection
customer shall submit updated models, if necessary, based on any changes to
the IBR plant design, equipment selection, protection and control changes, etc.
Any change to the IBR plant that affects the electrical output of the IBR plant
requires an updated set of models and a new model quality and performance test
report.  In general, any change that results in a Material Modification request or
Qualified Change review will trigger a new model submission. The specific

changes should be noted in the documentation (e.g., redline revisions). The
interconnection customer should inform MISO of any IBR plant changes
immediately for re-evaluation and determination of effects on the Definitive
Planning Process (DPP) system impact studies. The changes shall not degrade
the IBR plant performance for any tests listed in Section 5.
• Signed Generator Interconnection Agreement: Prior to execution of the
signed Generator Interconnection Agreement (GIA), the interconnection
customer shall submit all final models, including an additional PSS®E UDM, and
an accompanying model quality and performance test report. Updated site
information for short circuit ratio (SCR) and X/R ratio shall be used in this stage
and subsequent stages, when known. Any deviations between the models and
test report submitted at this phase and prior models and test reports used during
the DPP study process require re-evaluation by MISO and may require additional
consideration in subsequent queue system impact cluster studies. The final
submitted models establish a baseline performance expectation of how the IBR
plant should be designed.
• Commercial Operation Date: Within 60 days prior to the commercial operation
date (COD), the interconnection customer shall submit documentation that
demonstrates that the as-built equipment and parameterization matches the
dynamic models used during the study process (i.e., model verification). This
may include, but is not limited to, the following: screenshots, photos, inverter or
power plant controller (PPC) control mode and protection settings, nameplate
data, etc. If any equipment does not match the models submitted at signing the
GIA, the interconnection customer shall submit an updated set of models and an
updated model quality and performance test report.
•
Surplus and Replacement Interconnection Requests: The requirements listed
above are applicable to Surplus and Replacement interconnection requests at
the time of Interconnection Request, Generator Interconnection Agreement
signing, and Commercial Operation Date.

Figure 51: IBR Interconnection Modeling Requirements Process Flowchart
Any proposed changes that affect the electrical behavior, performance, or output of the
IBR plant require updated models, an updated model quality test report, and
benchmarked performance test report for all models. In general, any change that results
in a Material Modification request or Qualified Change review will trigger a new model
package submission. The specific changes should be noted in the documentation (e.g.,
redline revisions). Within 30 days of changes made to the IBR plant, the Generator
Owner (GO) shall submit an as-left verification report that verifies that the changes
made in the field match the models submitted. If the as-left changes differ from those
submitted to MISO and the TO, the GO will be subject to corrective actions outlined in
the MISO Tariff and applicable contractual agreements.
I-3 Definitions
The definitions in Clause 3.1 of IEEE Std 2800-2022 are applicable unless otherwise
defined in this document.
• Equipment-Specific Models – Models that represent the make, model, type,
and version of the installed (or planned) equipment. Equipment-specific IBR unit
models and plant-controller models are typically provided by the original
equipment manufacturer.
• Site-Specific Models – Equipment-specific models that also include the
parameters and settings of the installed (or planned) equipment in the field.
• Model Verification – The process of confirming that model structure and
parameter values represent the equipment or facility design and settings by
reviewing equipment or facility design and settings documentation [6].

• Model Validation – The process of comparing measurements with simulation
results to assess how closely a model’s behavior matches the measured
behavior [6].
I-4 Model Requirements
I-4.1 General Requirements for All Models
The model requirements listed in this section are applicable to all four model types (i.e.,
standard library, PSS®E/TSAT™ UDM, and PSCAD™ models). Model-specific
requirements for standard library, PSS®E/TSAT™ UDM, and PSCAD™ models are
listed in the next subsections.
1. The models shall be configured to match the installed (or planned) equipment in
the field and include all controls and protections (both software and hardware)
that could affect the electrical output of the IBR plant to the extent possible.
2. Submitted models shall be provided in standalone packages (i.e., one folder for
each model type containing all the necessary files), ready for simulations, and
shall represent the project at requested service level at the POI (i.e., maximum
active power output). The control mode and the parameters shall be set as
specified in applicable interconnection requests and contractual agreements.
3. The models shall have the capability to change the control mode to any control
mode possible in the actual power plant (e.g., voltage droop control, reactive
power control, or power factor control, etc.) with accessible and modifiable
reference setpoints.
4. All IBR units of the same type (identical design) shall be combined into a single
equivalent aggregated unit. All IBR unit transformers of the same type (identical
design) shall be combined into a single equivalent aggregated IBR unit
transformer. Figure 6Figure 2 shows a simplified single-line diagram of an
aggregated41 IBR plant for reference.


41 Aggregation should be used for identical designs and shall be avoided for differing types/designs. For example, if a PV plant uses two different solar
inverters, one equivalent aggregated unit shall be used for each type of inverter.

Figure 62. Simplified single-line diagram of an aggregated IBR plant.
5. The collector system model shall be an equivalent representation of the collector
system. The preferred equivalencing method of the collector circuits, IBR unit
transformers, and IBR units is detailed in [7][7].
6. All main power transformers and shunt compensation devices connected to the
medium voltage collector bus(es) shall be explicitly modeled (i.e., no
equivalencing).
7. The models shall include site-specific component and control models for the
following, as applicable:
a. IBR units,
b. IBR unit transformers,
c. Collector system,
d. Mechanically switched reactive power devices,42
e. Station service load,
f. Flexible AC transmission systems (FACTS) devices,43
g. Power plant controller,
h. IBR main transformer(s), and
i. Interconnection tie line.


42 E.g., shunt capacitor banks, shunt reactor banks, and harmonic filter banks.
43 E.g., STATCOM and SVC.

8. The PPC model shall include control of all devices that are controlled by the PPC
(e.g., batteries, different inverter manufacturers, switchable shunts, D-
STATCOM, etc.), if applicable.
9. The controls of mechanically-switched reactive devices shall be modeled if the
equipment dynamically responds to a disturbance within 10 seconds.
10. The controls of main power transformer on-load tap changers (OLTC/ULTC) shall
be modeled if the equipment dynamically responds to a disturbance within 10
seconds.
11. All components of the model shall be verified that they represent the installed (or
planned) equipment and settings. Attestations from the original equipment
manufacturers that the models represent the planned or installed equipment,
based on the available information at the time of submission, are required for the
IBR unit and the PPC. Complementary examples of acceptable approaches for
model verification include, but are not limited to, the following:
a. Mapping of controller’s code firmware version to the model version for
real-code models.
b. Evidence that the model parameters represent the planned control and
protection settings
12. The IBR unit models shall be validated to ensure that they represent the installed
(or planned) equipment and settings. This includes type test, factory acceptance
test, or hardware-in-the-loop (HIL) test results demonstrating a comparison of the
IBR unit’s response and the IBR unit’s model response for large-signal
disturbances and is typically provided by the original equipment manufacturer.
This is different from the plant level model validation that will be performed after
the commissioning of the plant.
13. Each set of models shall include documentation that:
a. Describe the applicability, functional use, and capabilities of the model.
b. Describe any known limitations of the models (e.g., minimum SCR, model
bandwidth, protection functions that are not included, control features that
are not modeled, etc.).
c. Identify a list of the files provided and their purpose (e.g., .obj, .dll, etc.).
d. Describe which PSS®E, TSAT™, and PSCAD™ versions are supported
(including Fortran Compiler for PSCAD™ models) and the minimum and
maximum simulation time steps and other relevant simulation parameters.

e. Provide an explanation of the control strategy of the PPC and the IBR unit
controllers together with the corresponding control block diagrams.
f. Define and describe parameters within the model that correspond to 1)
frequency droop, 2) frequency deadband, 3) voltage reactive power droop,
and 4) fault ride-through and protection settings.
14. All models shall be developed for a system with 60 Hz base frequency.
I-4.2 Requirements for Standard Library Models
The following requirements are applicable to only standard library models:
1. The models shall be compatible with PSS®E and TSAT™ versions specified by
MISO.
2. Only standard library models not listed as unacceptable by NERC [8][8], MISO,
or the Eastern Interconnection Reliability Assessment Group (ERAG) Acceptable
Model Working Group (AMWG) shall be used.
3. Any bus numbering larger than 1000 can be selected.
I-4.3 Requirements for PSS®E UDMs
The following requirements are applicable to only PSS®E UDMs:
1. The models and Dynamic Link Libraries (DLLs) shall be provided for PSS®E
versions specified by MISO.
2. The minimum timestep allowed is a quarter-cycle (i.e., 0.00416667 s).
3. Any bus numbering larger than 1000 can be selected.
4. Only table-driven models are acceptable (i.e., no CONEC and CONET
subroutines).
5. All modes within PSS®E UDM shall be accurately modeled including data
reporting mode (DOCU), data checking mode, data saving mode (DYDA).
6. The models shall be initialized at any feasible operating point without initial
condition suspect errors and without additional manual adjustments.
7. The models shall be dispatchable at any feasible operating point within
equipment capabilities.
8. The model shall allow multiple instantiations (i.e., several elements of the same
type shall be able to use the same DLL, where applicable).
9. The models shall allow “enabling headroom availability” for low frequency events.
This is different from dispatchability at different power levels.

10. Accompanying model documentation shall include:
a. A control block diagram representation of the model.
b. A full list of ICONs, CONs, STATEs and VARs and other relevant
parameters with descriptions.
c. A description of how to parametrize the dynamic model in case of power
flow changes (e.g., bus number, ID, etc.).
d. A description of how to enable headroom availability and its setpoint.
I-4.4 Requirements for TSAT™ UDMs
The following requirements are applicable to only TSAT™ UDMs:
1. A TSAT case (*.tsa) including power flow and dynamic files) and library files (*.dll
and *.tudm files) shall be provided for TSAT™ versions specified by MISO.
a. The TSAT *.tudm file should only define the structure of the model and
shall not include any project-specific information.
b. The TSAT *.dyr file should interoperate with the PSS®E *.dyr file.
2. The minimum timestep allowed is a quarter-cycle (i.e., 0.00416667 s).
3. Any bus numbering larger than 1000 can be selected.
4. The models shall be initialized at any feasible operating point without initial
condition suspect errors and warning messages.
5. The models shall be dispatchable at any feasible operating point within
equipment capabilities.
6. The models shall allow “enabling headroom availability” for low frequency events.
This is different from dispatchability at different power levels.
7. The models’ documentation shall include:
a. A control block diagram representation of the model.
b. A full list of parameters with descriptions.
c. A description of how to parametrize the dynamic model in case of bus
number changes.
d. A description of how to enable headroom availability and its setpoint.
I-4.5 Requirements for PSCAD™ Models
The following requirements are applicable to only PSCAD™ models:
1. The model shall include:

a. Grounding transformer(s), if used.
b. Over-voltage protection devices and filters, where applicable.
2. The IBR unit model shall:
a. Utilize the actual hardware control code, if possible.44
b. Represent the full detailed inner control loops of the power electronics.
c. Include the primary energy source (PES) model.
d. Include dc side dynamics, control, and protection of the converter.
e. Include a full power electronic switching device representation or an
averaged model representation of the converter.
3. The PPC model shall:
a. Utilize the actual hardware control code, if possible.446
b. Include all measurement, signal conditioning, communication delays, and
controller cycling delays, to the extent practical.
4. IBR unit transformer and IBR main transformer models shall include the
saturation characteristic of the core. This includes the per unit air core reactance,
the per unit knee voltage, and the per unit magnetizing current.
5. Interconnection tie lines less than 3 miles may be modeled as a PI section. A
Bergeron model or a frequency dependent model shall be used for longer
interconnection tie lines.
6. The model shall [10][10]:
a. Be compatible with PSCAD™ version 5.0.0 and higher.
b. Be compatible with Intel Fortran 32-bit and 64-bit compiler version 15 and
higher.
c. Be compatible with Visual Studio 2015 and newer.
d. Not require a simulation integration time step less than 10 μs.
e. Not require a specific simulation integration time step.
f. Be capable of reaching its ordered initial condition in less than 5 seconds
(simulation time).
g. Support the PSCAD™ “snapshot” feature.


44 Models that used the actual control code are commonly referred to as “Real Code” models [9][9].

h. Support the PSCAD™ “multiple run” feature.
i. Allow replication in different PSCAD™ cases or libraries through the
“copy” or “copy transfer” features.
j. Not use global variables in the PSCAD™ environment.
k. Not utilize multiple layers in the PSCAD™ environment, including
“disabled” layers.
7. The model should have pertinent control or hardware options45 accessible to the
user. Diagnostic flags46 should be accessible to facilitate analysis and should
identify why a model trips during simulations.
8. The PPC shall include accessibility of parameters that typically require site-
specific tuning.47
9. The site-specific model shall be included in an example test case that initializes
properly. The case shall include all equipment up to the POI. An ideal voltage
source behind an impedance may be used to represent the system equivalent for
the SCR at the POI.
I-4.6 Requirements for Parameter Verification
The following requirements are applicable to parameter verification for all IBR models.
The Parameter Verification Report shall be submitted:
a. With the signed GIA model submission as initial verification.
b. Within 60 days prior to COD as final verification of as-built settings.
c. Within 30 days of any parameter changes made after COD that affect the
electrical output of the IBR plant.
:

1. The interconnection customer shall submit a Parameter Verification Report
prepared by the OEM that demonstrates the model parameters match the
installed (or planned) equipment settings. The report shall include:


45 E.g., adjustable protection thresholds or real power recovery ramp rates.
46 E.g., flags to show control mode changes or which protection has been activated.
47 E.g., voltage controller gains.

a. Equipment make, model, and firmware version information that matches
the models used in site-specific interconnection studies.
b. A comprehensive parameter mapping table that correlates model
parameters (for both PSS^®^E/TSAT™ and PSCAD™ models) to field
device parameters, including:
• Scaling factors and unit conversions
• Parameter naming correlations between modeling platforms and
field devices
• Mathematical relationships for parameters that do not have direct
1:1 correspondence
c. As-built parameter settings exported directly from the commissioned (or
planned) IBR units, PPC, and other controlled devices.
d. Protection settings as implemented in the field (or as planned),
demonstrating conformance with applicable standards and interconnection
requirements.
e. Identification and justification of any differences between field (or
planned field) parameter settings and model parameter settings.
c. Include timestamp information for parameter exports.
2. The Parameter Verification Report shall be verified and approved by the
interconnection customer and/or Engineering, Procurement, and Construction
(EPC) contractor prior to commissioning. This approval shall confirm that:
a. All relevant inverter and PPC settings match those in the submitted
models.
b. The parameter mapping is complete and accurate.
c. Any identified discrepancies have been resolved or justified.
3. If discrepancies are identified between field parameter settings and model
parameter settings, the interconnection customer shall:
a. Update the as-built models to reflect the actual field settings; or
b. Update the actual field settings to reflect as-built models; or
c. Provide technical justification for maintaining different values in the models,
subject to MISO approval.

4. The interconnection customer shall incorporate parameter verification
requirements into OEM supply agreements, including:
a. Delivery of the Parameter Verification Report as specified above.
b. Provision of real-time parameter access capabilities.
c. Support for parameter verification activities throughout the equipment
lifecycle.
5. For parameters that cannot be directly verified through field device exports (e.g.,
aggregated or derived parameters), the Parameter Verification Report shall
include:
a. Description of the methodology used to determine these parameters,
b. Supporting calculations, curve-fitting results, or statistical analyses; and
 c. OEM attestation confirming the accuracy of the derived parameters.

6. The Transmission Owner, Planning Coordinator, and Transmission Planner are
encouraged to use these parameter verification requirements when defining as-
built facility model verification and performance validation requirements for the
interconnection customer, ensuring that the parameters, control modes, and
equipment modeled in interconnection studies have been properly implemented
at the facility.
I-5 Model Quality and Performance Tests
The following requirements apply:
• A single-machine-infinite bus (SMIB) system shall be used for all tests, where the
IBR plant is connected to a Thevenin equivalent system. The SCR and value of
Thevenin voltage source of the equivalent system are defined for each test.
o Where applicable and as defined in grid initial conditions, an SCR of 3 and an
X/R ratio of 5 shall be used for model quality tests associated with the initial
interconnection request. This may differ from the interconnection study SCR
and X/R assumptions which are based on actual system location. The model
quality tests at signed GIA and COD should use the site-specific SCR and X/R,
as available.
o A value listed as “variable” indicates that any value may be used.

• IBR generation plants (i.e., not storage) reactive power dispatch assumptions Qmin
and Qmax should be zero and 32.87% of the IBR continuous rating, respectively.
Battery energy storage system IBR plants Qmin and Qmax should be -32.87% of the
IBR continuous rating and 32.87% of the IBR continuous rating, respectively.
• All tests shall be run for a minimum simulation duration of 30 seconds and the
results shall be plotted for the time from 0 to 30 seconds.
• Frequency, voltage, active power, and reactive power shall be plotted at the point of
measurement (POM) in separate figures for each test (i.e., four figures for each
test). Relevant Trip control signals shall be included in the related plot (e.g.,
frequency tripping shown on frequency plot).
I-5.1 Quality and Performance Tests for All Models
The simulation tests described in this section shall be performed for the four models
(i.e., standard library models, PSS®E UDM, TSAT™ UDM, and PSCAD™ models). The
following requirements also apply:
• The results of each test for all the four models (i.e., standard library model, PSS®E
UDM, TSAT™ UDM, and PSCAD™ model) shall be overlaid on the same plot axis
to facilitate comparison between different models (i.e., maximum of four curves on
each figure).
• Any major discrepancies between the results obtained from different models for
each figure shall be explained and justified otherwise they will be rejected by MISO.

I-5.1.1 Initialization Tests
Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fa
il
Active
Power at
the POM
Reactive
Power at
the POM
Voltage at
the POM
(pu)
Infinite
Bus
Voltage
SCR
05.1.1-1
No
disturbance
Pmax
Qmax
1.0
Variable
3

05.1.1-2
No
disturbance
Pmax
Qmin
1.0
Variable
3

05.1.1-3
No
disturbance
Pmin48
Qmax
1.0
Variable
3

05.1.1-4
No
disturbance
Pmin4810
Qmin
1.0
Variable
3


Pass/Fail Criteria
The models pass these tests if all the following conditions are met for each test:
a. PSS®E and TSAT™ models initialize without any initial suspect error and the
results remain flat during the simulation run.
b. PSCAD™ models shall reach a steady state in less than 5 seconds and remain
flat during the remainder of the simulation run.
c. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.




48 Applicable only to BESS plants. Pmin implies the maximum allowable charging (absorption) active power level.

I-5.1.2 Balanced Fault Ride-Through Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial
Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.2-
1
Bolted 3LG fault
Pmax
Qmax
1.0
Variable
3


Disturbance
• Bolted 3LG fault: A three-phase-to-ground fault with zero fault impedance is applied
at the POM at t=10 seconds and cleared after 10 cycles (i.e., 0.167 seconds).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
d. If the plant enters momentary cessation (current blocking) mode, it shall resume
current injection in no less than 5 cycles following voltage recovery.
e. After fault clearing and voltage recovery within the normal range, the active
power recovery time to the pre-fault value shall be within 1.0 second.
f. Appropriate reactive current response shall be observed based on control
settings.
g. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.3 Small Voltage Disturbance (SVD) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.3-
1
Small voltage
disturbance
Pmax
0
Figure
7Figure
3
N/A
3


Figure 73: Voltage profile at the POM for the SVD tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the voltage
profile shown in Figure 7Figure 3 (i.e., use the playback model in PSS®E/TSAT™ and
controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip.
b. The plant shall have a stable and well-damped response. An acceptable
damping ratio is 0.3 or greater [5][5].
h. The plant shall not enter momentary cessation (current blocking) mode.
i. Appropriate reactive power response shall be observed based on control
settings.
j. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.4 Small Frequency Disturbance (SFD) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.4-
1
Small frequency
disturbance
50% Pmax
+ no
headroom49
0
Figure
8Figure
4 (b)
N/A
N/A

05.1.4-
2
Small frequency
disturbance
50% Pmax
+
headroom
(50% of
Pmax)50
0
Figure
8Figure
4 (b)
N/A
N/A



(a) High frequency

(b) Low frequency
Figure 84: Frequency profile at the POM for the SFD tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the
frequency profile shown in Figure 8Figure 4 (i.e., use the playback model in
PSS®E/TSAT™ and controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:


49 The resource should be modeled with no additional power available.
50 The resource should be modeled with available power equal to Pmax.

a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. Appropriate active power response shall be observed based on control settings,
including droop and deadbands.
c. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.5 High-Voltage Ride-Through (HVRT) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.5-
1
High voltage
Pmax
Qmin
Figure
9Figure
5
N/A
3


Disturbance
Voltage at the POM is stepped from 1.0 pu to 1.19 pu at t=10 seconds and return to 1.0
pu after 1 second (i.e., at t=11 seconds), as shown in Figure 9Figure 5.

Figure 95: High voltage profile at the POM for the HVRT tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the voltage
profile shown in Figure 9Figure 5 (i.e., use the playback model in PSS®E/TSAT™ and
controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. The plant shall not enter momentary cessation (current blocking) mode.

c. If active power is reduced, it should recover to the pre-disturbance value within
1.0 second after the disturbance.
d. Appropriate reactive current response shall be observed based on control
objectives.
e. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.6 Low-Voltage Ride-Through (LVRT) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.6-
1
Low voltage
Pmax
Qmax
Figure
10Figure
6
N/A
3



Figure 106: Low voltage profile at the POM for the LVRT tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the voltage
profile shown in Figure 10Figure 6 (i.e., use the playback model in PSS®E/TSAT™ and
controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. The plant shall not enter momentary cessation (current blocking) mode.
c. If active power is reduced, it should recover to the pre-disturbance value within
1.0 second after the disturbance.
Time
Duration (s)
Voltage Level at the
POM (pu)
0.32/0.16*
0.00
1.20
0.25
3.00
0.50
6.00
0.70
*for IBR plants with auxiliary equipment that
cause ride-through limitations, 0.16 seconds
may be used

d. Appropriate reactive current response shall be observed based on control
settings.51
e. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.




51 By default, the IBR unit shall operate in reactive current priority mode during high- and low-voltage ride-through events [5][5].

I-5.1.7 High-Frequency Ride-Through (HFRT) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.7-
1
High
frequency
Pmax
0
1.0
N/A
N/A


Figure 117: High frequency profile at the POM for the HFRT tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the
frequency profile shown in Figure 11Figure 7 (i.e., use the playback model in
PSS®E/TSAT™ and controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. Appropriate active power response shall be observed based on control settings.
c. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.8 Low-Frequency Ride-Through (LFRT) Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial
Condition
Pass/Fail
Active Power
at the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.8-
1
Low
frequency
50% Pmax
0
1.0
N/A
N/A


Figure 128: Low frequency profile at the POM for the LFRT tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the
frequency profile shown in Figure 12Figure 8 (i.e., use the playback model in
PSS®E/TSAT™ and controllable voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. Appropriate active power response shall be observed based on control settings.
c. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.9 Protection Verification Tests

Test No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage at
the POM
(pu)
Infinite
Bus
Voltage
SCR
05.1.9-1
High voltage
Pmax
0
Figure 9
(a)
N/A
N/A

05.1.9-2
Low voltage
Pmax
0
Figure 9
(b)
N/A
N/A

05.1.9-3
High
frequency
Pmax
0
Figure 9 (c)
N/A
N/A

05.1.9-4
Low
frequency
Pmax
0
Figure 9
(d)
N/A
N/A


Disturbances
• Voltage at the POM is stepped from 1.0 pu to 1.5 pu at t=10 seconds and then
returns to 1.0 pu at t=15 seconds. See Figure 13Figure 9(a).
• Voltage at the POM is stepped from 1.0 pu to 0 pu at t=10 seconds and then
returns to 1.0 pu at t=15 seconds. See Figure 13Figure 9(b).
• Frequency at the POM is stepped from 60 Hz to 70 Hz at t=10 seconds and then
returns to 60 Hz at t=15 seconds. See Figure 13Figure 9(c).
• Frequency at the POM is stepped from 60 Hz to 50 Hz at t=10 seconds and then
returns to 60 Hz at t=15 seconds. See Figure 13Figure 9(c).


(a) High voltage

(b) Low voltage

(c) High frequency

(d) Low frequency
Figure 139: Voltage and frequency profiles at the POM for the protection verification tests.


Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and apply the voltage
and frequency profiles shown in
Disturbances
• Voltage at the POM is stepped from 1.0 pu to 1.5 pu at t=10 seconds and then
returns to 1.0 pu at t=15 seconds. See Figure 13(a).
• Voltage at the POM is stepped from 1.0 pu to 0 pu at t=10 seconds and then
returns to 1.0 pu at t=15 seconds. See Figure 13(b).
• Frequency at the POM is stepped from 60 Hz to 70 Hz at t=10 seconds and then
returns to 60 Hz at t=15 seconds. See Figure 13(c).
• Frequency at the POM is stepped from 60 Hz to 50 Hz at t=10 seconds and then
returns to 60 Hz at t=15 seconds. See Figure 13(c).


(e) High voltage

(f) Low voltage

(g) High frequency

(h) Low frequency
Figure 13Figure 9 (i.e., use the playback model in PSS®E/TSAT™ and controllable
voltage source in PSCAD™ at the POM).

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant is generally expected to trip unless inverter, PPC, and plant relays are
proven to be set outside these operating conditions.
b. Active, reactive, and voltage values shall reasonably match between standard
library, PSS®E/TSAT™ UDM, and PSCAD™ models at the POM.

I-5.1.10 Short Circuit Ratio (SCR) Tests

Test No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.1.10-
1
SCR change +
Bolted 3LG fault
Pmax
0
1.0
Variable
Figure
14Figure
10


Disturbance
Change the SCR of the grid, as shown in Figure 14Figure 10. Apply a three-phase-to-
ground fault with zero fault impedance at the POM and clear the fault after 6 cycles (i.e.,
0.1 seconds). The SCR step change shall be simultaneous with the fault clearing.
MISO suggests a default value of 10 seconds between faults, though the time should be
chosen to allow settling from the prior fault before initiating another fault.

Figure 1410: Example of short circuit ratio profile of the grid for SCR tests.
Grid Initial Condition
Assume an ideal voltage source at the POM to represent the grid and change the SCR
as shown in Figure 14Figure 10.

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response for an
SCR ≥ 3 (i.e., time 55 seconds in Figure 14Figure 10). An acceptable damping
ratio is 0.3 or greater [5][5].
b. Active, reactive, and voltage values shall reasonably match between PSS®E
standard library, PSS®E UDM, and PSCAD™ models at the POM.

I-5.2.1 Quality and Performance Tests for PSCAD™ Models Only
The simulation tests described in this section shall be performed for PSCAD™ models
only.

Phase Angle Change Tests

Test
No.
Disturbance
IBR Plant Initial Condition
Grid Initial Condition
Pass/Fail
Active
Power at
the POM
Reactive
Power at
the POM
Voltage
at the
POM (pu)
Infinite
Bus
Voltage
SCR
05.2.1-
1
Phase angle
±25° change
Pmax
0
1.0
Variable
3


Disturbance
Run the simulation for t=10 seconds. Apply the corresponding phase angle change (i.e.,
±25 degrees) in the positive sequence phase angle of system voltage at t=10 seconds
and continue the simulation run until t=30 seconds.

Pass/Fail Criteria
The models pass these tests if all the following conditions are met:
a. The plant shall not trip and shall have a stable and well-damped response. An
acceptable damping ratio is 0.3 or greater [5][5].
b. The plant shall not enter momentary cessation (current blocking) mode.

I-6 References

[1] FERC, “Order 2023 – Improvements to Generator Interconnection Procedures and
Agreements,” July 28, 2023. Available: https://www.ferc.gov/media/e-1-order-2023-rm22-
14-000.
[2] NERC, “Reliability Standards for the Bulk Electric Systems of North America,” online:
https://www.nerc.com/pa/Stand/Pages/ReliabilityStandards.aspx
[3] MISO, “Attachment X: Appendix 6 to Generator Interconnection Agreement (GIA)” 103.0.0,
Effective On: November 14, 2024.
[4] Power System Dynamic Performance Committee, “Stability definitions and characterization
of dynamic behavior in systems with high penetration of power electronic interfaced
technologies,” Technical Report (PES-TR77) April 2020. [Online]. Available:
https://resourcecenter.ieee-pes.org/publications/technical-
reports/PES_TP_TR77_PSDP_stability_051320.html.
[5] “IEEE Standard for Interconnection and Interoperability of Inverter-Based Resources (IBRs)
Interconnecting with Associated Transmission Electric Power Systems,” in IEEE Std 2800-
2022, vol., no., pp.1-180, 22 April 2022, doi: 10.1109/IEEESTD.2022.9762253.
[6] NERC Project 2020-06 Verifications of Models and Data for Generators. Available:
https://www.nerc.com/pa/Stand/Pages/Project-2020_06-Verifications-of-Models-and-Data-
for-Generators.aspx
[7] E. Muljadi, A. Ellis, et al, “Equivalencing the Collector System of a Large Wind Power
Plant”, IEEE Power Engineering Society Annual Conference, Montreal, Quebec, June 12-
16, 2006.
[8] NERC, “Dynamic Modeling Recommendations – Recommended Modeling Practices and
List of Unacceptable Models,” July 2023. Available:
https://www.nerc.com/pa/RAPA/ModelAssessment/Documents/Dynamic%20Modeling%20
Recommendations.pdf.
[9] WECC Meeting, “IEEE/Cigre Power System DLL Models/Standard,” April 5, 2019.
Available: https://www.electranix.com/wp-content/uploads/2019/04/Use-of-Real-Code-in-
EMT-Models-for-WECC.pdf.
[10] Electranix, “PSCAD Model Requirements Rev. 12,” September 19, 2022. Available:
http://www.electranix.com/wp-content/uploads/2022/09/PSCAD-Model-Requirements-Rev.-
12-Sept-2022.pdf

I-7 Example MQT Report
Model Quality Test Report- Example
J9999 Superior Gale Wind Project
DPP-2026
Executive Summary
A Model Quality Test (MQT) was performed for the J9999 Wind Project, as specified by the
MISO BPM-015 Appendix I- IBR Modeling Requirements. This version of the report represents
the dynamic models submitted at application/in phase 2/as-left using the latest versions of the
TSAT UDM, PSSE UDM, Generic Models, and EMT models provided by the OEM.

Models were provided by the OEM on June 1st, 2026. Models were updated based on as-left
settings during commissioning. Models were benchmarked, and simulation results are provided
in this report.

The tests and benchmarking reveal consistent performance between all four model types under
all tests except in the Small Voltage Disturbance test (test # 3-1), where the generic model
indicated unsatisfactory performance compared to the UDM and EMT models.
Methodology and Assumptions
The dynamic models consist of a single equivalent aggregated generation unit representing 25
WindPower W150 wind turbines, a single equivalent aggregated transformer unit representing
25 6 MVA padmount transformers, an equivalent representation of the collector system, an
explicitly modeled main power transformer, and additional equipment modeled according to
section 4 of Appendix I.

Model Quality Test Results
The model quality tests were performed as described by MISO’s BPM-015 Appendix I. Table 1
provides a summary of the results.

Test #
Description
Generic UDM
EMT
5.1.1-1
Initialization Tests- No Disturbance.
Pmax/Qmin
Pass
Pass
Pass
5.1.1-2
Initialization Tests- No Disturbance.
Pmax/Qmin
Pass
Pass
Pass
5.1.1-3
Initialization Tests- No Disturbance.
Pmin/Qmax
N/A
N/A
N/A
5.1.1-4
Initialization Tests- No Disturbance.
Pmin/Qmin
N/A
N/A
N/A
5.1.2-1
Balanced Ride-Through Tests
Pass
Pass
Pass
5.1.3-1
SVD Tests
Fail
Pass
Pass
5.1.4-1
SFD Tests- No Headroom, HiFreq
Pass
Pass
Pass
5.1.4-1
SFD Tests- No Headroom, LoFreq
Pass
Pass
Pass
5.1.4-2
SFD Tests- Headroom, HiFreq
Pass
Pass
Pass
5.1.4-2
SFD Tests- Headroom, LoFreq
Pass
Pass
Pass
5.1.5-1
HVRT Test
Pass
Pass
Pass
5.1.6-1
LVRT Test
Pass
Pass
Pass
5.1.7-1
HFRT Test
Pass
Pass
Pass
5.1.8-1
LFRT Test
Pass
Pass
Pass
5.1.9-1
Protection Verification- High Voltage
Pass
Pass
Pass
5.1.9-2
Protection Verification- Low Voltage
Pass
Pass
Pass
5.1.9-3
Protection Verification- High Frequency
Pass
Pass
Pass
5.1.9-4
Protection Verification- Low Frequency
Pass
Pass
Pass
5.1.10-1
SCR Tests
Pass
Pass
Pass
5.2.1-1
Phase Angle Change Tests (EMT Only)
Pass
Pass
Pass

Discussion of Failed Results
Test 3-1: Small Voltage Disturbance
The generic model failed the Small Voltage Disturbance test due to inappropriate reactive power
response for elevated voltages. This is a known limitation when trying to use generic models for
this turbine. It is the OEMs recommendation to use the UDM52.
Benchmarked Results of Tests53
1-1 Initialization Tests: Pmax/Qmax





52 UDMs and EMT models are expected to pass all tests. Due to the inherit limitations of generic models, some failures that cannot be
corrected with model tuning are anticipated and do not necessarily indicate an invalid set of models.
53 partial set of results- submitted report should include all plots for all tests

1-2 Initialization Test: Pmax/Qmin

2-1 Balanced Ride-Through Tests

3-1 Small Voltage Disturbance Tests



*Additional plots for all tests should be provided in actual submission*
