---
doc_id: bpm-015-r33-clean
section_id: 06
section_title: Definitive Planning Phase Processes and Methodologies
start_page: 61
end_page: 125
status: current
source_pdf: 01_bpm-015-r33_generator_interconnection_clean.pdf
---

# 06 Definitive Planning Phase Processes and Methodologies

6.
Definitive Planning Phase Processes and Methodologies
6.1. Generator Interconnection System Impact Study
A SIS will be conducted which will include thermal analysis, short circuit analysis, transient and
voltage stability analysis. The SIS will provide a list of facilities (including Interconnection
Facilities, Network Upgrades, Distribution Upgrades, Generator Upgrades, Common Use
Upgrades, Shared Network Upgrades, and, if such upgrades have been determined, upgrades
on Affected Systems) that are required as a result of the IR. The study may also include system
protection, and loss analyses depending on the recommendation from the ad hoc group. SIS
results will include a preliminary indication of the planning level estimate of cost and length of time
that would be necessary to implement any Network Upgrades identified in the analysis. The
Network Upgrades may be identified to accommodate a group of generators together, wherever
applicable.

6.1.1.
Steady State Analysis
The Steady State Analysis will include the evaluation of system performance under both normal
and contingency conditions for all new generation IRs, including energy storage devices, in
accordance with Reliability TPL Standards. The Steady State Analysis will generally include the
following analyses:
i.
Thermal analysis
ii.
Voltage analysis
iii.
PF requirement analysis
iv.
Prior outage analysis

For IRs related to energy storage devices, MISO will evaluate the plant for an entire range of
operation by testing the plant as a generator and a load.

6.1.1.1 Thermal analysis
Steady State Thermal analysis will be performed by adhering to all applicable standards as
discussed below in Section 6.1.1.1.2. A new ad hoc study group will be formed and chaired by
MISO for each study. MISO will determine, with input from the ad hoc group, the monitored
element and contingency lists and other study assumptions. Based on the recommendations and
input received from the ad hoc group, facilities in the Affected Systems that could potentially be
impacted by the interconnection are monitored. For any identified significantly affected facility, the
study will determine transmission upgrades and/or transmission alternatives required to mitigate
the constraints for full power output. Development of solutions for identified transmission issues
will consider transmission upgrades, including Storage As Transmission-Only Asset (SATOA),
and transmission alternatives like planned generation re-dispatch, reconfiguration, load shed, or
Remedial Action Scheme (RAS) on a comparable basis consistent with Attachment FF and
Section 4.3.1.2 of the Transmission Planning BPM (BPM-020).

The study case will undergo a DC screen to identify monitored element and contingency pairs
which are significantly loaded (e.g., ninety percent (90%) or more). The loadings will be recorded
for the bench case and study cases and DFs will be calculated by using the Monitored Sensitivity
function in PSS MUST. All monitored elements and contingency pairs which are overloaded
(worst case loading) in the study case using AC analysis and which meets the criteria in Section
6.1.1.1.6 will be reported.

To mitigate a constraint, MISO will check the MTEP appendices and discuss with the impacted
TO(s) to determine if there already exists a planned project, including approved load
interconnection projects, which will alleviate the constraint. A Long Range Transmission Planning
(LRTP) project included in an approved Multi-Value Project (MVP) Portfolio can only replace a
previously identified Network Upgrade as constraint mitigation if that LRTP project is the same
facility as the identified upgrade (i.e., same connecting substations at identical voltage); this is to
avoid a full model build and restudy that would be required by including the MVP Portfolio.

In the case when an approved load interconnection is utilized to mitigate a constraint, only the
Network Upgrade(s) associated with the load interconnection will be documented as conditions
in the Generator Interconnection Agreement (GIA).

If there is no such planned or proposed project, MISO will work with the impacted TO(s) and ICs
to identify a solution consistent with baseline planning solution development described in Sections
4.3.1.2 and 4.3.1.3 of BPM-020, subject to the concurrence of MISO, the TO(s) and ICs. If a
project(s) resolves the constraint, and that project(s) is approved by the Board within (1) calendar
year of the GIA execution or execution of an amendment thereof, then the IC will not be
responsible for upgrade(s) that would resolve the constraint, but the MTEP project will be included
as a GIA contingent facility. If that project(s) is not approved within one (1) calendar year of the
GIA execution or execution of an amendment thereof, the IC will be responsible for those
transmission upgrade(s).

6.1.1.1.1.
Bench Case Development
The bench case (pre-project case) will be created by considering the most recent MTEP 5 year
out LBA dispatch case as the base starting case. Any approved projects (in MTEP Appendix A)
and projects recommended by MISO for Board approval (e.g., recommended short-term
Transmission Plan defined in BPM-020) will be included in the Base Cases. Additionally, the
most recent portfolio of Long Range Transmission Planning projects will be included in the
bench case of the next DPP cycle following Board approval if Board approval is granted at least
30 Calendar Days before the DPP Phase 1 study kick off.

•
The higher queued generators (without a GIA) added to the starting case and dispatched at
their expected output level as per fuel type as shown in Table 6-1 such that higher queued
generators in MISO North (Classic) are sunk into MISO North (Classic) and generators in
MISO South are sunk into MISO South8 and generators in Affected System are sunk into the
same area or subregion, if applicable, as they are modeled by the host RTO such as the
existing generation is scaled down by the amount of MW of the higher priority queued
generator(s) added. The study cycle generators and associated interconnection facilities are
added to the bench case, but the study generators are not dispatched in the bench case. Units
that have had GIAs signed after MTEP model development, but prior to study kickoff will be
dispatched utilizing the same methodology as higher queued generators.

6.1.1.1.2.
Study Case Development
•
The study case (post-project case) will be created by starting with the bench case, but then
dispatching the study generator(s) at their expected output level described in Table 6-1 and
then scaling down the non-study cycle generation in MISO North or MISO South or Affected
System(s) by the amount of study cycle MW added.



8 After dispatching generators per fuel type, the total generation in MISO North (Classic) and MISO South and the Affected
System shall be equal to total generation in the respective region as seen in the starting MTEP case. This ensures that the
total load & losses in a region are being served by total generation in the respective region and thereby implicitly respecting
the N-S constraint/transfer limit.

Table 6-1 Dispatch per Fuel Type for Study and Higher Queued Generators (without a GIA)
Fuel Type under Study and
Higher Queued
Summer Peak Dispatched as % of
Interconnection Service
Shoulder Peak Dispatched as % of
Interconnection Service
Combined Cycle
100%
50%
Combustion Turbine
100%
0%
Diesel Engines
100%
0%
Hydro
100%
100%
Nuclear
100%
100%
Storage9
100%10
 - 100%, 0% 9,10
Steam – Coal
100%
100%
Oil
100%
0%
Waste Heat
100%
100%
Wind
18.1 %11
100%
Solar
100%
47 12
 Hybrid Facility13 (Any
combination of the above fuel
types except Battery which can
be assumed up to 100%
dispatchable in both Summer
Peak and Shoulder Peak)
Battery up to 100% Last Fuel
Dispatched
Other Fuels based on above dispatch
assumptions of each fuel type with any
adjustment based on requested
interconnection Service14
Battery Up to 100% Last Fuel
Dispatched
Other Fuels based on above dispatch
assumptions of each fuel type with any
adjustment based on requested
interconnection Service15

Any other seasonal model with appropriate load and generation dispatch level, if required to
adequately assess the system reliability in the region, may replace one or more of the cases listed
above.


9 Storage requests that indicate the need to charge from the grid will be studied at their maximum charging capability.
Transmission Service is required to charge from the Transmission System; the GIA does not grant Transmission Service. In
order to obtain any type of Transmission Service for charging from the Transmission System, the IC will have to seek service
as a Transmission Customer.
10 For cycles before the DPP 2022 cycle, Storage dispatch in the shoulder peak case will continue to use the previous value
of +/-100%
11 Dispatch level for wind resources will be aligned with wind capacity credit used in the MTEP summer peak case. It was
15.6% in 2017 MTEP summer peak case. This value is subject to change based on the wind capacity credit which is
calculated annually.
12 For cycles before the DPP 2019 cycle, Solar dispatch in the shoulder case will continue to use the previous value of 50%
13 A hybrid facility is a Generating Facility that utilizes more than one fuel source to inject power on to the Transmission System.
This Generating Facility can be any combination of the fuel types in Table 6-1. For e.g., Solar + Storage, Wind + Storage,
Solar + Wind, CC + Solar, Solar + Wind + Storage etc. This is inclusive of Surplus, Replacement, and Generator expansion
requests that incorporate additional fuels. Batteries are last fuel dispatched in a hybrid configuration limited by either the
Battery installed capacity or requested service level in both Peak and Shoulder Peak Cases.

14 See Examples in Appendix E
15 See Examples in Appendix E

Table 6-1 above describes the fuel type dispatch levels for individual fuel type in summer peak
and shoulder peak models for the DPP studies. The following assumptions will be used, as
applicable, for hybrid facilities16:

i.
The fuel type dispatch levels of Table 6-1 will be used for each corresponding fuel type in
hybrid facilities except that, if the total Generating Facility output per fuel type dispatch in
both summer peak and shoulder peak steady state models is below the total
Interconnection Service requested, then the Generating Facility will be dispatched in such
a way that total requested Interconnection Service is studied in at least one of the study
models. The study model with the highest generation output after doing fuel type dispatch
will be chosen to study the full requested Interconnection Service.
ii.
For steady state models, generators will be reduced proportionally if the dispatched MW
per fuel type dispatch is greater than Interconnection Service requested.
iii.
For stability analysis, Section 6.1.2 of this BPM will be followed to determine the scenarios
to be studied. By default, the generators will be reduced proportionally if the dispatched
MW is greater than the Interconnection Service requested, and all generators will be online
even at a reduced output. Generally, only discharging mode of storage will be studied in
the stability analysis as the stability and control model are the same regardless of direction
of real power flow17. Additional scenarios for stability analysis may be studied based on
technologies used, if necessary.
iv.
Short circuit analysis will be conducted with all units connected for the installed MVA
(irrespective of MW service requested).
v.
The Interconnection Customer can specify whether they plan to charge the storage
devices from the Transmission System in the Generator Interconnection (GI) application
(Appendix 1 to Attachment X). If the IC specifies that they will not charge from the
Transmission System, then this will be documented in the GIA. For this type of request,
the “charging” mode of storage will not be studied in the DPP studies18.
Should an Interconnection Customer with an executed GIA prohibiting use of the
Transmission System to charge later desire to charge from the Transmission System, this
may be reevaluated by entering the storage facility into a subsequent queue cycle, procuring
long-term Transmission Service to serve the desired amount of charging load, or by working
with the relevant Transmission Owner and/or Load-Serving Entity for study and submittal into
MISO’s annual MTEP process.


16 Appendix E of this BPM includes a few possible dispatch scenarios for hybrid facilities. In reality, there are many possible
combinations of hybrid facility, which may or may not be captured in Appendix E. Therefore, based on engineering judgement,
MISO may include other scenarios to assess the impact of the hybrid facility to the Transmission System, if necessary.
17 This is applicable to hybrid facility with storage and standalone storage requests.
18 This is applicable to hybrid facility with storage and standalone storage requests.

vi.
The dispatch assumptions for hybrid facility will be applicable for all generators behind the
same Point of Interconnection irrespective of a single hybrid application or separate GI
applications for the same owner.

6.1.1.1.3.
Generation to Include
The SIS bench and study case will include the following queued generation projects, including
energy storage devices, in the region:
i.
All projects with a GIA.
ii.
All projects that have a DPP Queue Position and their associated Network Upgrades.
iii.
All queued projects on the Affected System (in the Generator Interconnection queue
of the other Transmission or Distribution Providers) will be modeled per MISO and
Affected System joint agreements.

Generators requesting Retirement or Suspension under MISO Attachment Y process are notified
about their approval by a letter from MISO upon completion of the necessary studies. Such
generators will be treated as follows:
i.
Generators under study will be modeled available for dispatch up to their
interconnection service level.
ii.
Generators with approved Attachment Y Notices that have not waived their
interconnection rights (i.e., suspended) will be modeled offline for three (3) years
beginning on their start date and be available for dispatch after the three (3) years
based on the information provided by the Generator Owners through the Attachment
Y Notice.
iii.
Generators with approved Attachment Y Notices that have waived their
interconnection rights (i.e., retired) will be modeled offline beginning on their
Attachment Y start date and remain offline indefinitely based on the information
provided by the Generator Owners through the Attachment Y Notice.
iv.
Generators designated as SSRs will be modeled available for dispatch up to their
interconnection service level until the latest in-service date of system improvements
necessary to ensure system reliability as listed in the Attachment Y study report.

6.1.1.1.4.
Applicable Reliability Criteria
FAC-002-2 standard requires a reliability impact assessment of new or materially modified
generating facility, on the transmission system, to be undertaken and results coordinated with
TOs, Load Serving Entities, Transmission Providers other Affected Systems. To ensure
compliance with NERC reliability standard FAC-002-2, all applicable Regional, sub-regional,
Power Pool and individual system local transmission planning criteria will be used to ensure that
the assessment includes steady state, short circuit, and dynamic studies as necessary to evaluate

system performance under both normal and contingency conditions19 in accordance with reliability
TPL standards.

All applicable NERC TPL and FAC standards can be referenced at the following link:
http://www.nerc.com/docs/standards/rs/Reliability_Standards_Complete_Set.pdf

6.1.1.1.5.
Cascading Outage Conditions
Based on the ad hoc group’s recommendation, select events may be studied to identify potential
cascading outage conditions. After taking appropriate NERC/ERO/Regional action, including the
controlled reduction of generation, load and curtailing firm transfers, if the transmission facility is
still overloaded, then additional upgrades may be required to alleviate the condition (Refer to
section 6.1.1.1.2 for details pertaining to applicable reliability criteria).

6.1.1.1.6.
Prior Outage Conditions
Based on the ad hoc group’s recommendation, and in compliance with 6.1.1.1.2, contingency
analysis in the local area will be performed for selected prior outage conditions. The purpose of
this review is to identify operating restrictions or additional Network Upgrades to prevent
unreliable operating conditions under prior outage conditions. In the event that a RAS or an
operating plan in accordance with local planning criteria cannot be developed to prevent
cascading uncontrolled outages, either a permanent reduction in generation (i.e., a relay scheme
that trips the synchronizing breaker past a certain MW level) or a Network Upgrade may be
identified.

The output of this study will be an appendix to the Interconnection SIS report. Also, the results of
this study may be included in the operating sections of the appendices to the Interconnection and
Operating Agreement.

6.1.1.1.7.
Permissible Software Tools
Siemens PTI’s PSS/E and PSS MUST software for power system studies will be used to perform
the studies. MISO will use in-house software tools in conjunction with PSS/E and PSS MUST to
generate and post-process the study results. MISO may consider using other industry accepted
power system analysis software tools with similar capabilities.






19 The System Impact Study includes only select contingencies, based on inputs from the ad-hoc study group, for which system
adjustments are permitted as per the TPL standards.

6.1.1.1.8.
Criteria Used to Determine Constraints
In order to obtain any type of Interconnection Service, all generators, including energy storage
devices, must mitigate injection constraints identified in the study. A constraint is identified as an
injection constraint if:
i.
The generator has a larger than twenty percent (20%) sensitivity factor on the
overloaded facilities under post contingent condition (see NERC TPL) or five percent
(5%) sensitivity factor under system intact condition, or
ii.
If LRTP projects are included in the study cases in MISO sub-regions, 6.1.1.1.8.ii.a
and/or 6.1.1.1.8.ii.b constraint criteria shall be applicable.
a. The generator has a larger than ten percent (10%) sensitivity factor on the
overloaded less than 345 KV MISO Midwest facilities under post contingent
condition (see NERC TPL) or five percent (5%) sensitivity factor under system
intact condition.
b. The generator has a larger than ten percent (10%) sensitivity factor on the
overloaded less than 345 KV MISO South facilities under post contingent condition
(see NERC TPL) or five percent (5%) sensitivity factor under system intact
condition.
iii.
The overloaded facility or the overload-causing contingency is at generator’s outlet, or
iv.
The MW impact due to the generator is greater than or equal to twenty percent (20%)
of the applicable rating (normal or emergency) of the overloaded facility, or
v.
For any other constrained facility, where none of the Study Generators meet one of
the above criteria in i, ii or iii, however, the cumulative MW impact of the group of study
generators is greater than twenty percent (20%) of the rating of the facility, then only
those study generators whose individual MW impact is greater than five percent (5%)
of the rating of the facility and has DF greater than five percent (5%) (i.e., power
transfer distribution factor (PTDF) or outage transfer distribution factor (OTDF)) will be
responsible for mitigating the cumulative MW impact constraint, or
vi.
Impacts on Affected Systems would be classified as Injection constraints based on the
Affected Systems’ criteria.
vii.
Any other applicable TO FERC filed Local Planning Criteria.

Further, the Generating Facilities, including energy storage devices, requesting NRIS must
mitigate constraints under system intact and single contingency conditions, by using the
deliverability algorithm, if the generator impact (incremental flow caused by the generator) is equal
to or greater than five percent (5%) of the net injected power into the grid.

Mitigations for a NERC TPL multiple contingency events will be determined in accordance with
reliability criteria identified in 6.1.1.1.2. Engineering judgment may be used for special cases.

6.1.1.1.9.
Deliverability Analysis
For the purpose of Deliverability Analysis, impacts of higher queued or pre-existing requests for
ERIS will not be considered unless they have a confirmed firm transmission service reservation
associated with the generator. In that case, only the level of firm transmission service will be
modeled in the Base Case when studying a lower queued project for deliverability. NRIS will be
evaluated at one hundred percent (100%) of the requested capability of the IR, including those
for energy storage devices. NRIS will be granted for the amount for which a generator commits
to build the Network Upgrades, up to the requested capability of the IR, as identified through the
deliverability analysis. The IC must choose the NRIS level prior to the completion of IC Decision
Point II. Once the IC chooses a NRIS MW level, that MW amount will be used in the Final SIS in
DPP Phase III.

The methodology for deliverability analysis can be found in Appendix C of this BPM.

6.1.1.1.10. Network Upgrade Cost Allocation

6.1.1.1.10.1.  Thermal Network Upgrade Cost Allocation
The Network Upgrades cost for a set of projects (one or more sub-groups or entire group with
identified Network Upgrades) will be allocated based on the MW impact from each project on the
constrained facilities in the Study Case. The highest MW impact for each individual project on the
constraint will be used in the calculation. All thermal constraints will be identified and a DF from
each project, including energy storage devices, on each constraint will be obtained. Finally, the
cost will be allocated based on the pro rata share of the MW impact on all constraints from each
project, including energy storage devices where MW impact = DF * Gen Output of the project in
the model where the constraint occurs. If the Network Upgrade alleviates multiple constrained
facilities the cost is allocated based off the sum of the highest MW contribution on all of the
constrained elements for the DPP project under contingency. If a project doesn’t violate DPP
reliability criteria for a constrained element, their MW impact = 0 for calculation purposes.

Table 6-2 provides a simple example of the cost allocation methodology described in this section.

Table 0-2 Example of Thermal Project Cost Allocation
Constraint
Mitigation
MW Impact Project 1
MW Impact Project 2
Overload of Line A
New Line X ($50M)  6
3
Overload of Line D
New Line X ($50M)   12
15
Overload of Line H
New Line X ($50M)   4
0
Total MW Impact
New Line X ($50M)   22
18
Cost Allocation

=(22/40*50) = $27.5M
=(18/40)*50 = $22.5M

Note that the allocation is applicable to the Network Upgrade cost only; each project will be
responsible for the cost of Interconnection Facilities required to connect to the Transmission
System. In order to save time and effort a more simplistic approach can be used for the purpose
of cost allocation as long as the new method is acceptable to all parties and does not delay the
study process.

6.1.1.1.10.2.
Voltage Network Upgrade Cost Allocation
Cost allocation of voltage constraint driven Network Upgrades will be determined by the pro rata
share of the voltage impact each project has on the most constrained bus under the most
constraining contingency. The voltage impact of each project will be calculated by locking all
voltage regulating equipment in the model and then backing out each project one at a time to
identify each project’s impact to the constraint. In severe instances of voltage collapse where
projects cannot be backed out one at a time, they will be added one at a time to determine their
impact to the constraint.

Table 6-3 provides a simple example of the cost allocation methodology described in this
section.

Table 0-3 Example of Voltage Project Cost Allocation Methodology
6.1.1.1.10.3.
Transient Stability Network Upgrade Cost
Allocation
Transient stability driven Network Upgrades will be cost allocated based on the pro rata share of
the total MW request of all the projects causing instability. The project(s) causing instability will
be determined by backing out each project one at a time to identify each project’s impact to the
constraint.

6.1.1.1.10.4.
Complex Cost Allocation
As the number and types of constraints increases, mitigating the constraints individually may
result in higher overall costs. In instances when mitigation(s) resolve multiple types of
Project
Contingent
Voltage
with all
DPP
Projects
Δ Voltage
with DPP
Project
removed
New
Voltage
Type
Cost Allocation %
Gen A
0.75
0.01
0.76
Harmer 33.33%
Gen B
0.02
0.77
Harmer 66.67%
Gen C
-0.01
0.74
Helper
0.00%
Total
0.03

100.00%

constraints (such as thermal + voltage or thermal + voltage + transient stability) the cost is
allocated based off the ratio share of the total cost of the independent mitigation types in order
to equitably allocate the cost to all parties contributing to constraints. In summary, only the
lowest cost mitigation option will be constructed, but for cost allocation purposes the
independent mitigations are required.

Table 6-4-1 and 6-4-2 provides an Example of Complex Cost Allocation

Table 0-4-1 Example of Independent Project Cost
Constraint
Independent
Mitigation
Cost
(M$)
Project
Branch U
Overload
Rebuild
Branch U
$30M
Gen A
Branch V
Overload
Rebuild
Branch V
$25M
Gen B
Bus Y Low
Voltage
Capacitor
Bank
$1M
Gen C
Gen D –
Transient
Instability
Build New
Line Bus S
to Bus T
$204M  Gen D
Total Cost
$260M

Table 0-4-2 Example of Complex Cost Allocation Methodology
Constraint
Best Fit
Solution
Cost (M$)
Project
Branch U
Overload
Build
New
Line
Bus S
to Bus T
((30/260)*204)
= $23.54M
Gen A
Branch V
Overload
((25/260)*204)
= $19.62M
Gen B
Bus Y Low
Voltage
((1/260)*204) =
$0.78M
Gen C
Gen D –
Transient
Instability
((204/260)*204)
= $160.06M
Gen D
Total Cost
$204M

6.1.1.1.10.5.
Generator Interconnection Backbone Network
Upgrade
In some instances, initial system conditions are so severe that the DPP model isn’t in a usable
state until Network Upgrades are added. GI Backbone Network Upgrades are the upgrades that
are necessary in order to obtain a usable DPP model. Transmission Line GI Backbone Network
Upgrades are cost allocated per the pro rata share of MW contribution of DPP projects on the
constraints being alleviated by the GI Backbone Upgrades. Capacitor Bank and SVC GI
Backbone Network Upgrades are cost allocated based off of the voltage change at the most
constrained bus when each project is removed one at a time. In severe instances where
projects cannot be backed out one at a time, they will be added one at a time to determine their
impact to the constraint.

Table 6-5-1 and 6-5-2 provides an Example of GI Backbone Network Upgrade

Table 0-5-1 Example of GI Backbone Network Upgrade Constraint Identification
Constraint
Upgrade
MW
Impact
Project
A
MW
Impact
Project
B
MW
Impact
Project
C
Total
MW
Impact
Overload
of Line A-B
New
Line 1
($100M)
5
10
0
15
Overload
of Line D-
E
New
Line 2
($200M)
10
20
5
35
Low
Voltage
Bus G
Cap
Banks
($5M)
.01
.005
-.02
(helper)
.015


Table 0-5-2 Example of GI Backbone Network Upgrade Cost Allocation Methodology

Upgrade
Cost Allocation
Project A
Cost Allocation
Project B
Cost Allocation
Project C
New Line 1
($100M)
(5/15) * 100M =
$33.33M
(10/15) * 100M =
$66.67M
0
New Line 2
($200M)
(10/35) * 200M =
$57.14M
(20/35) * 200M =
$114.29M
(5/35) * 200M =
$28.57M
Cap Banks ($5M)
(.01/.015) * 5M =
$3.33M
(.005/.015) * 5M =
$1.67M
0





6.1.1.1.11. Shared Network Upgrade Cost Allocation Eligibility

The Shared Network Upgrades are the Network Upgrades funded by an IC that are or will be in-
service prior to the Commercial Operation date submitted by the IR under study, or are otherwise
far enough along that it is not practical to bring the IR under study into an MPFCA for the upgrade.

As part of the SIS MISO will review the proposed configuration of the study generators, including
energy storage devices, and perform a test, if required, to determine their eligibility for cost
sharing. The set of Shared Network Upgrades included in the test will be all GIP facilities in-
service for a period of less than five (5) years, and costs greater than or equal to $10 million.

If a generator meets any of the following two criteria, it will share the cost of the Shared Network
Upgrade without any further tests:
i.
The generator connects to the Shared Network Upgrades
ii.
The generator connects to a substation where the Shared Network Upgrade(s) terminates.

For all other generators that do not meet the above criteria, further analysis will be performed to
measure their use of and benefit from the Network Upgrades previously identified and funded by
other generators. The intent of the test is to determine if the new generators under study are
benefiting from a Network Upgrade previously identified for a different generator and should share
in the cost of that Network Upgrade.

A power flow analysis will be performed to calculate the impacts of the study generators on the
Shared Network Upgrades under system-intact conditions. The following two screening criteria
will be used to make the decision.
i.
If the impact of the IR on a generator funded Network Upgrade is greater than 5 MW AND
is greater than one percent (1%) of the facility rating, the following additional screening will
be performed.
ii.
If the impact of the IR on a generator funded Network Upgrade is greater than five percent
(5%) of the facility rating OR the power transfer distribution factor (PTDF) is greater than
twenty percent (20%), the generator will share the cost of the Network Upgrade, now
designated as a Shared Network Upgrade.

The flowchart in Figure 6-1 visually describes the whole methodology for determining the eligibility
for cost sharing. The Shared Network Upgrades the new generator is responsible for will be listed
in Appendix A of their GIA.

Exempt from
cost sharing
Is the POI on the
eligible NU?
Is the POI on a sub
where an eligible NU
terminates?
Share the NU
cost
Calculate the
Impact (I)
Is I>5 MW ?
Is I>1% of the
facility rating ?
Is PTDF>20% ?
Is I>5% of the
facility rating ?
Yes
Yes
No
No
No
No
No
Yes
Yes
Yes
Yes
No

Figure 6-1 Flowchart describing the methodology to identify the Late Comer projects.




6.1.1.2.
Steady State Voltage Analysis
Voltage analysis will be performed on the selected contingencies generated from the DC screen
or contingencies deemed relevant to the analysis. Bus voltages outside of the defined limits
(based on the LBA criteria) in the post case will be recorded and compared to the Base Case

values. Bus voltages will be considered voltage constraints if, for a given contingency, the bus
voltage is outside of the allowed voltage range for the post case and is at least 0.01 per unit worse
than the Base Case voltage for the same contingency.

6.1.1.3.
Power Factor Requirement and Low Voltage Ride Through
Analysis for Wind Generation Plants
PF and Low Voltage Ride Through (LVRT) analysis will be performed to determine the
requirements for a new Wind Generation Plant according to FERC Orders 661/661-A, FERC
Order 827, and Appendix G of the pro forma GIA. MISO will use the following methodology in
determining the final requirements as determined during the SIS.
i.
To determine the PF requirements for a Wind Generation Plant, MISO will model each
Wind Generation Plant under study at unity PF at the POI (no reactive capability). If
voltage criteria violations at the POI exist, then MISO will enforce the criteria laid out
in FERC Orders 661/661-A, thereby modeling the plant at the more stringent of 0.95
leading and lagging PF capability at the POI or the TOs’ interconnection guidelines PF
requirements. Should no voltage criteria violations exist, MISO will model the inherent
capability of the Turbines at the POI using the best available IC supplied data, and
proceed with the studies.
ii.
For a new Generating Facility, MISO will request the IC to demonstrate compliance
with the FERC Order 827 requirement. The associated modeling will be applied in the
study model.
iii.
A Wind Generation Plant must be able to remain online during select system
disturbances. To test the LVRT capability of a Wind Generation Plant, MISO will
evaluate the plants’ performance for the following faults:
a. Three phase faults with normal clearing
b. Single Line to Ground faults with delayed clearing

If violations are found, the IC will be required to submit updated LVRT settings to ensure that the
LVRT threshold is maintained at the POI. The Wind Generating Plant will be required to remain
online for the specified time intervals.


6.1.2.
Short Circuit and Stability Analysis
Short circuit analysis will generally include determining the fault current contribution from the new
Generating Facility and its Network Upgrades under three-phase fault and single line to ground
fault conditions. The study will identify any circuit breaker(s) that would need to be replaced to
accommodate fault currents from the proposed Generating Facility.

The stability study will include the evaluation of the impact of the new Generating Facility on
transient stability performance of the system by adhering to the reliability standards under
6.1.1.1.2. The stability study may also consider other scenarios to assess system transient
stability in accordance with the local transmission planning criteria and Section 4.5 of this BPM.

Additionally, based on engineering judgement, MISO may include other scenarios to assess
system transient stability when all generators in the same electrical area (local area) as the study
generator(s) are at their full ERIS level. The IC will only be responsible for mitigating constraints
which are caused by the study generators.

Example:
The base case used for the stability study will be dispatched with all generators local to
the study generator(s) to their full ERIS injection capacity.

The study case will be created by adding the study generator(s) to the base case.

The IC will only be responsible for constraints which appear in the study case but do not
appear in the base case.

For wind turbine generators LVRT analysis would be done according to FERC Orders 661 and
661-A.

6.1.2.1.
Base Case Assumptions

6.1.2.1.1.
Load Levels
The Stability Study will be performed using a season and load level that traditionally represents
the most limiting conditions for system stability in the region.

6.1.2.1.2.
Generation to Include
Refer to Section 6.1.1.1.1.2.

For the short circuit analysis, queued generation will be added only in the area close to where the
proposed generation is being added. Since the fault current contribution from a generator decays
quickly the deeper you go into the system, the network changes electrically remote from the POI
may be ignored for the purpose of short circuit analysis.

6.1.2.2.
Applicable Reliability Criteria
Refer to Section 6.1.1.1.2.

6.1.2.3.
Permissible Software Tools
Siemens PTI’s PSS/E software for power system studies will be used to perform the studies.
MISO may use the in-house software tools/scripts or regionally accepted software programs to
generate the results with PSS/E and post-process them. MISO may consider using other industry
accepted power system analysis software tools with similar capabilities.

For short circuit analysis, PSS/E, Aspen, CAPE, or any other industry accepted software tools
with similar capabilities may be used.

6.1.2.4.
Criteria Used to Determine Stability and Short Circuit Constraints
Stability Study
All conditions/disturbances leading to the Generating Facility or system instability in compliance
with the applicable reliability standards in 6.1.1.1.2 will be documented as a constraint. If there is
regional or TO’s FERC filed planning criteria for transient period voltages or post transient voltage
recovery, it will be monitored and, any violation caused by the proposed interconnection will be
flagged as a constraint.

Short Circuit Study
All breakers over-dutied (underrated) after the addition of the proposed Generating Facility will be
flagged.

6.1.2.5.
Mitigation Used to Resolve Stability Constraints
MISO will coordinate and seek feedback from the ad-hoc group to identify and implement
appropriate mitigation recommendations, for observed criteria violation in 0. This mitigation may
include, but not limited to, the transmission reinforcement, faster breakers, new breakers,
additional static or dynamic reactive support, an operating guide or RAS in accordance with local
planning criteria depending on the type of disturbance causing the constraint.

6.1.3.
Mitigation Verification
Sensitivity analyses will be performed by modeling Network Upgrades identified in all SIS
analyses to verify that the recommended mitigation does not cause any new reliability violations.
If it is determined that the coordinated and recommended mitigation plan causes further reliability
violations on the transmission system, then the IC will be provided various alternatives as follows.
i.
IC can agree to fund these additional upgrades and proceed to the Facilities phase of
the GIP.
ii.
IC can proceed with the alternative mitigation plan that does not cause reliability
violations.

6.1.4.  Storage Charging from the Grid

If a storage interconnection application indicates that it will charge from the grid, it will be modeled
at its default maximum charging capability in the DPP Shoulder Peak charging case as shown in
Table 6.1. For system constraints that appear only in the DPP Shoulder Peak charging case,
limiting the battery charging rate(s) is an acceptable mitigation option. Any lower charging limit
identified would be documented in the GIA as a control scheme requirement.

GIA-enforced charging limits may be evaluated for modification or removal following the
generation interconnection process by re-entry into a subsequent interconnection queue cycle,
procurement of long-term Transmission Service to serve the desired amount of charging load, or
by working with the relevant Transmission Owner and/or Load-Serving Entity for study and
submittal into MISO’s annual MTEP process.

6.1.5.
Customer Funded Optional Study
Any existing IC can request an optional study, as pursuant to Section 10 of the Attachment X of
the MISO Tariff. The purpose of these technical studies is to provide additional information to the
IC that is normally outside the scope of a typical SIS. MISO initially charges a sixty-thousand-
dollar ($60,000) study deposit to perform such optional studies and then may request, if
necessary, additional funds to complete the study.

6.1.5.1.
Background
The Generation Interconnection SIS results identify reliability constraints that must have a
mitigation plan prior to the execution of a GIA. Depending on the individual generator impact and
the type of the requested interconnection service, there could be a situation where a reliability
constraint is identified in the SIS report, but the IC is exempt from mitigating the constraint if its
impact is below the threshold as identified in Section 6.1.1.1.6.

Therefore, despite not being responsible for paying for Network upgrades, identified in the SISs,
an IC’s generation facility can get curtailed in Real Time for the same constraint under varying
operating environments. Therefore, to evaluate potential options to reduce Real Time congestion
and curtailment for their respective generating facilities, ICs can request an Optional
Interconnection Study by providing a detailed scope.

Since Optional Interconnection Studies are outside the scope of regular SISs and are performed
out of regular interconnection study cycles, the results of any such analysis are non-binding.

6.1.5.2.
Network Upgrade Funding and Facilities Studies
If the IC(s) decide to fund the network upgrades, to mitigate the identified constraints identified in
the Optional Interconnection Study, MISO will then facilitate the coordination with applicable TO.
With applicable agreements between IC and TO(s) in place, MISO will include these network

upgrades within its MISO Transmission Expansion Plan (MTEP) as “Other – MP Funded” project.
MISO will work with applicable TOs to conduct a Facility Study. Facility Study timelines and cost
would be consistent with Section 6.2 of this BPM.

6.1.5.3.
MISO Sub-Regional Planning Meetings
Where a Market Participant (MP) requests and funds a Facility Study, MISO staff will notify all
stakeholders at its upcoming applicable Sub Regional Planning Meeting. Further, when necessary
FCAs are in place, MISO staff will notify all stakeholders at a subsequent SPM and include in
MTEP as “Other - MP Funded” project.

6.1.5.4.
Availability of ARRs
ICs can request MISO Auction Revenue Rights (ARRs) associated with funded transmission
expansions. This will be handled by the Financial Transmission Rights (FTR) group consistent
with BPM-004.

6.1.5.5
Shared Network Upgrade Cost Allocation Treatment
Pursuant to Section III(A)(2)(a) of Attachment FF, a MP or a group of MPs are allowed assume
cost responsibility to fund a network Upgrade on the Transmission System. However, any
upgrade that is funded by the IC that was not identified as a required Network upgrade, during
the Generation Interconnection Study process, will not qualify for the Shared Network Upgrade
treatment as noted in Section 6.1.1.1.9.

6.1.6.
External Network Resource Interconnection Service Study
This product gives Generating Facilities external to MISO the ability to procure NRIS under the
MISO Tariff as long as it meets certain conditions.

To be eligible for study, the Generating Facility must have a signed Interconnection Agreement
with the interconnecting Transmission Provider or be in commercial operation at the time of the
request. Additionally, the Application Fee (D1), DPP Study Funding deposit (D2) and the DPP
Entry (M2) Milestone deposit are required at the time of application for an external NRIS study
request. Upon the receipt of a valid application, the request will be placed in the next applicable
DPP cycle.

Deliverability studies will be processed in the same manner as any other Generating Facility
requesting NRIS under MISO’s tariff. MISO will perform all applicable ERIS reliability analysis as
outlined in Section 6.1.1.1.2 to ensure system reliability for the injection from the Generating
Facility external to MISO. In conjunction, a deliverability study will also be performed as outlined
in Section 6.1.1.1.6.

The qualifying NRIS amounts will be memorialized through a MISO Service Agreement that will
be filed at FERC. If any conditional service is granted, such service will be subjected to the annual
interim studies outlined in Section 6.6. Generating Facilities requesting external NRIS must also
procure firm Transmission Service to the MISO border through the host interconnecting
Transmission Provider prior to the execution of a Service Agreement and such firm Transmission
Service should be maintained for the duration of the Service Agreement.

6.2. Facility Study
The Facility Study will determine the cost and time estimate to construct the Network Upgrades
and TO’s Interconnection Facilities necessary to physically and electrically interconnect the
proposed Generating Facility to the Transmission System.

The Facilities Study will be broken down into two stages, the Interconnection Facility facilities
study and Network Upgrade facilities study. The Interconnection Facility facilities study will be
done in parallel with the DPP Phase II SIS and the Network Upgrade facilities study will be done
after the DPP III SIS is complete. The combination of the two facilities studies will determine the
cost and construction schedule of identified Network Upgrades and Interconnection Facilities for
each project in the DPP.

6.2.1.
Study Objectives
For facility improvements determined from the SIS and based on the official POI:
i.
Design and specification of facility improvements in accordance with Good Utility
Practice and applicable planning and design criteria. These criteria must be
consistently applied to all existing and proposed generation projects in an LBA.
ii.
Development of detailed cost estimates that include equipment, engineering,
procurement, and construction costs according to the level of accuracy possible based
on the proposed in-service date of the projects.
iii.
Identification of the electrical switching configuration of the connection equipment,
including, but not limited to the transformer, switchgear, meters, and other station
equipment.
iv.
Identification of the nature and estimated cost of any TO’s Interconnection Facilities
and Network Upgrades, System Protection Facilities and Distribution Upgrades on the
Transmission System and Affected Systems necessary to accomplish the
interconnection.
v.
An estimate of the time required to construct facilities and required phasing of
improvements, if any.
vi.
Preparation of the draft Appendices to the Interconnection Agreement/Facilities
Construction Agreement with completed exhibits

Generally, the TOs with facilities needing upgrades identified in the SIS will determine the
construction and cost estimate of those upgrades and/or Interconnection Facilities. Cost
estimates will be determined to a +/- twenty percent (20%) margin if the lead time to the in-service
date for the required facilities does not exceed eighteen (18) months. For studies requiring cost
estimates for longer lead items, a good faith estimate will be developed. To the extent the IC
requests a cost estimate with a smaller margin of error, and the TO can reasonably obtain that
estimate without holding up other projects in the DPP, then the estimate will be within the
negotiated margin.



6.2.2.
Scope of Upgrades
The Facilities Study will clearly describe, and list various upgrades required to interconnect the
proposed Generating Facility. The report should include the following Exhibits to include in
Appendix A of the GIA:
i.
Exhibit A1: (IC provides to Consultant) IC Generating Facility and IC constructed
Interconnection Facilities. This would include IC Single Line or Elementary One-line
Diagram(s) and system Maps depicting and identifying the POI, meter point(s),
metering and relaying CT arrangements, the Ownership demarcation(s).
ii.
Exhibit A2: (Consultant develops) TO single line or Elementary One-line Diagram(s)
and system Maps depicting and identifying the POI, meter point(s), metering and
relaying CT arrangements relative to the Interconnection, the Ownership
demarcation(s), the TO Interconnection Facilities, Network Upgrades, Stand-Alone
Network Upgrades, System Protection Upgrades and Affected System Upgrades.
iii.
Exhibit A3: (Consultant develops) a Site Plan and/or General Arrangement drawing
showing the entire interconnection substation complete with all transmission line
structures impacted by the new substation. This drawing will be based on and
developed from the IC provided certified site survey drawing.
iv.
Exhibit A4: (Consultant develops) a basic Plan and Profile drawing showing the
required line tap work associated with the interconnection sub or switching station.
This drawing will be based on and developed from the IC provided certified site survey
drawing.
v.
Exhibit A5: (Consultant develops) a categorized list or tabulation of TO Interconnection
Facilities, non-Stand-Alone Network Upgrades, Stand-Alone Network Upgrades,
System Protection Upgrades and Affected System Upgrades to be constructed by the
TO.
vi.
Exhibit A6: (Consultant develops) a categorized detailed cost breakdown of facilities
identified in Exhibit A5 as by TO, by major component (e.g., transformer, line terminal,

breaker, etc.) and by subcomponent (e.g., lightning arrester, disconnect switches,
protection equipment, communication equipment, monitoring and alarm equipment,
metering facilities, grounding, special controls, or equipment needed to meet stability
or short circuit criteria, etc.) Similarly, each transmission line should be subcategorized
by ROW acquisition needs (new/existing and major/minor) and the major and minor
components.


6.2.3.
Cost of Upgrades
The Facilities Study will provide a breakdown of various components of Network Upgrades and
Interconnection Facilities required to interconnect the proposed Generating Facility. The report
should include the following Exhibits to include in Appendix A of the GIA:
i.
 Exhibit A7: (Consultant develops) a categorized tabulation of TO Interconnection
Facilities, Non-Stand-Alone Network Upgrades, Stand-Alone Network Upgrades,
System Protection Upgrades to be constructed by the IC.
ii.
Exhibit A8: (Consultant develops) a categorized detailed cost breakdown of facilities
identified in Exhibit A7 as by the IC by major component (e.g., line terminal, etc.) and
by subcomponent (e.g., breaker, lightning arrester, disconnect switches, protection
equipment etc.).
iii.
Exhibit A9: (Consultant develops) Total categorized cost estimate for TO
Interconnection Facilities and Network Upgrades (Stand-Alone and non-Stand-Alone)
including a list or tabulation of Interconnection Network Upgrades (Stand-Alone and
non-Stand Alone) that are subject to the Attachment FF treatment. There is no refund
for radial facilities from network to the Generating Facility.

6.2.4.
Conditions to GIA (Appendix A10)
The Facilities Study report identifies the cost and schedule of Network Upgrades that are identified
for Interconnection projects. In addition to these upgrades, MISO may identify other conditions
which may include other higher or similarly queued IRs, other MTEP assumptions embedded in
the study case, Distribution Upgrades, or System Protection Upgrades for higher or similarly
queued projects.
i.
Exhibit A10: MISO will perform analysis on the GI study case and monitor upcoming
MTEP upgrades that are not yet in service based on the following Criteria:
a. DF ≥ 5% AND
b. MW Impact ≥ 5 MW, AND
c. MW Impact ≥ 1% of the Facility Rating

All Network Upgrades identified in the SIS, required to mitigate Voltage and Stability related
issues, will be included in the Appendix 10 to the GIA.

Upcoming MTEP projects applicable to study GI project(s), proposed for voltage & stability
purpose, will be listed.

6.2.5.
Facility Study Exhibits for the GIA
The Facilities Study report will include the following exhibits to describe the Milestones,
Construction and Coordination Schedule for the proposed interconnection. These exhibits will be
included in the Appendix B of the GIA:
i.
Exhibit A11 (IC provides): A list of key projects and regulatory activities that must be
met by the IC after receipt of the final GIA for the project to maintain its queue position
or mutually agreeable in-service schedule. The IC must provide evidence of continued
Site Control for Generating Facilities; Site Control for Interconnection Facilities and
Network Upgrades after execution of the GIA (Section 7.2.2 of the GIP) The IC must
also provide evidence that one or more of the following items are in development within
one hundred eighty (180) Calendar Days of receiving the final GIA: 1) contract for the
supply or transportation of fuel to the Generating Facility; 2) contract for the supply of
cooling water to the Generating Facility; 3) contract for engineering services,
construction services, or generating equipment; 4) contract for the sale of electric
energy or capacity from the Generating Facility; or 5) application for state and local
air, water, land or federal nuclear permits and that the application is proceeding per
regulations.
ii.
Exhibit A12 (Consultant develops): Construction and Coordination Schedule of the
Generating Facility, IC Interconnection Facilities, the TO Interconnection Facilities,
Network Upgrades (subcategorized by non-Stand-Alone and Stand-Alone Network
Upgrades) identifying long lead items, outage issues and expected critical path
coordination items. Identify activity start dates, duration of activity and expected
completion dates for all major components.
•
Identify Progress Payments
•
Identify start-up and test responsibilities.
•
Identify TO permitting process.
•
Identify issues including right-of-way acquisition for new transmission lines or
substations.
iii.
Exhibit A13 – (Consultant Develops) List of affected TO activities and schedules
necessary to obtain regulatory approval for facilities to be provided by affected TO(s).

6.2.6.
Interconnection and Operating Guidelines

The study report should include any “project specific” guidelines or requirements for the
interconnection and/or operation of the Facility that go beyond the generic and universal
requirement of “Good Utility Practice.” These requirements/guidelines may include topics such as
System Protection Facilities, communication requirements, metering requirement(s), grounding
requirements, transmission line and substation connection configurations, unit stability
requirements, equipment ratings, short circuit requirements, synchronizing requirements,
generation and operation control requirements, data provisions, energization inspection and
testing requirements (if applicable), the unique requirements (if any), of the Transmission Owner
to which the facility will be physically interconnected, switching and tagging, data reporting
requirements, training, capacity determination and verification (including Ancillary Services and
certification), emergency operations, including system restoration and black start arrangements,
identified must-run conditions, provision of Ancillary Services, specific transmission requirements
of nuclear units to abide by all NRC requirements and regulations, stability requirements, including
generation short circuit ratio considerations, limitations of operations in support of emergency
response, maintenance and testing, and any other specific requirements not listed above.

All such Interconnection and Operating Guidelines must be included in Appendix C to the GIA.

6.2.6.1.
Interconnection Agreement Appendices Populated
The Facilities Study report must include the Exhibits A1 through A13 of the GIA populated in draft
format. These exhibits must go through legal review by the TO prior to publishing the report.
Having these draft GIA exhibits in the Facilities Study report will provide a good starting point for
the development of the GIA and will make the GIA review process smoother and less time
consuming.

6.2.7.
Submittal of IA for Appendix Review
 MISO recommends early negotiation requests after Decision Point II and issuance of the draft
Phase II Interconnection Facilities Study under Attachment X, Section 11.1 to allow ample time
for negotiations. Except when IC requests early or delayed negotiation or, when further Facilities
Studies are required (FCA/MPFCA), MISO will tender to the IC and TO a draft GIA and, as
applicable, draft FCA(s) and/or MPFCA(s), together with draft appendices completed to the extent
practicable, within five (5) Business Days after issuance of the applicable first portion of the
Interconnection Facilities Study report and final System Impact Study report: Negotiation Meeting:
The purpose of this meeting will be to discuss the Appendices to the GIA/FCA/MPFCA. MISO will
provide these documents for review at least five (5) Business days prior to the date comments
are due. The participants are expected to review the technical information in the draft appendices
to the GIA/FCA/MPFCA and provide any comments to MISO at least two (2) Business Days prior
to the meeting. If required, additional negotiations will be handled primarily outside of a formal

meeting. Follow Up Meeting: If requested, MISO will host an additional formal meeting to discuss
any remaining details requiring person to person communications.
Five (5) Business Days after the start of negotiations, the IC shall provide:
i.
Its initial payment option pursuant to Article 11.5 of the GIA, and
ii.
IC’s desired, In-Service Date, Initial Synchronization Date, and Commercial Operation
Date, if different from the dates in the Facility Study Report.

These dates will be used to complete the cash flow payments and Milestones in Appendix B of
the GIA.

6.2.8.
Submittal of GIA/FCA for Execution / Filing Unexecuted
Compliant with Attachment X, Section 11.3, MISO will circulate the final GIA and FCA (if
applicable) to all parties for execution. If there is a deviation in pro-forma Agreement, the GIA/FCA
will be filed with FERC after execution by all parties. Otherwise, the MISO will maintain the
executed agreement and notify FERC via its next Electric Quarterly Report (EQR). If the GIA
negotiations result in an impasse, MISO will file the Agreement unexecuted with FERC no later
than ten (10) Business Days from the date of party(ies) declaring an impasse.

6.2.9.
Provisional Generator Interconnection Agreement
IC can request a PGIA for a project for a limited operation of the plant at any time through IC
Decision Point II, or if the schedule becomes delayed by more than sixty (60) Calendar Days
between Decision Point II and the end of the Facilities Studies. An IC must meet all of the following
conditions before a PGIA will be offered:
i.
All planning studies identifying system impacts and mitigations have been completed
in accordance with NERC and applicable regional reliability criteria through a
Provisional Interconnection Study
ii.
Project has met all Milestones in the process (i.e., D1, D2, M1, M2, M3, and M4. The
M3 and M4 deposits will be eight thousand dollars ($8,000) per MW of the IR if not
already calculated)
iii.
Facility Study has been completed for the required Interconnection Facilities for the
project or if there are existing Interconnection Facilities that can be used for the project
without any modifications.
iv.
IC agrees to install equipment or protective devices that would disconnect the
Generating Facility in the event the output of the Generating Facility exceeds the
operational limit described in the PGIA.
v.
IC agrees to assume all risks and liability associated with the changes in the
Interconnection Agreement including but not limited to the change in output limit and
additional costs for Network Upgrades

Under the PGIA, the maximum permissible output of the Generating Facility will be determined
based on the incremental transfer capability available at the POI to the MISO footprint. Such limit
will be identified on the Base Cases used for Available Flowgate Capacity (AFC) calculations
under Attachment C of the MISO OATT. Analysis to identify the operational limit for provisional
GIA will be performed after IC meets all process Milestones for the project. The operational limit
for the Generating Facility under provisional GIA will be reviewed and updated as required on a
planning year quarterly basis.

6.2.9.1.
Provisional Interconnection Agreement Limit Methodology
The MISO methodology for calculating operating limits for all generators requesting
interconnection service by executing a PGIA uses a two-pronged approach as follows:
i.
A MUST DC transfer analysis will calculate DFs of all generators that have greater
than 20% (OTDF) and a 5% (PTDF) impacts on all constraints.
ii.
These DFs will be used to calculate the operating limits, in addition to other constraints
as demonstrated in the examples that follow, by utilizing Microsoft Excel Solver
optimization tool. Examples are shown in Section 6.2.9.1.3.
except that a constraint should not be considered as a limit if the LODF (Line Outage Distribution
Factor) value between the overloaded element and the unfinished contingent facility from GIA
Exhibit A10 is less than 20%. This LODF screening does not apply if the overloaded element in
this analysis, or the unfinished contingent facility, is directly connected at the generator’s POI.

In order to implement this methodology, there are several inputs and assumptions that must be
addressed that are outlined below.
6.2.9.1.1
PSSE Base Case Assumptions
i. MISO will use a seasonal near-term MTEP model and adjusted to match the study horizon.
The adjustments will be strictly limited to the dispatch of QOL units to the Annual ERIS
level and the change in generation will be offset based on their merit order within the same
LBA. Transmission and generation outages lasting ≥ 60% of the study quarter will be
included only in the binding quarter. Approved retirements and suspensions will be
modeled offline.
ii. No changes will be made to the load pattern in the case.
iii. No changes will be made to any other generator dispatch.
iv. No changes will be made to the case topology.

6.2.9.1.2
Input Files and Analysis Assumptions
i.
MISO will use N-1 Contingencies to evaluate the DFs for each unit on all constraints.
ii.
MISO will use monitored files for all facilities above 34 kV.
iii.
MISO will use the most current available generator information and use the Pmax and
Pmin based on the generator limits provided.

6.2.9.1.3
Generator Output Optimization Equations
The main concept behind this technique is to optimize the summation of Initial Flow of each
constraint and the individual MW impact of each PIA generator on that constraint, such that the
optimized flow on the monitored element is less than or equal to the Emergency rating of the line
under the key contingencies being studied. Also, while optimizing the flow on constrained
facilities, the generator limits are used as constraints such that the generation output is maximized
for each optimized constrained flow. In other words, the desired solution would try to maximize
the output of each unit such that the flow on the constrained element will be equal to or less than
the rating of the monitored element.

EQUATION SETUP WITH CONSTANTS AND VARIABLES

Y1 = Unit 1
Y2 = Unit 2
C1 = Total flow on Monitored element of Constraint 1
C2 = Total flow on Monitored element of Constraint 2
C3 = Total flow on Monitored element of Constraint 3
C4 = Total flow on Monitored element of Constraint 4
Cn = Total flow on Monitored element of Constraint n
Ygen1 = Output of Unit 1
Ygen2 = Output of Unit 2
Ymax1 = Maximum Output of Unit 1
Ymax2 = Maximum Output of Unit 2
Ymin1 = Minimum Output of Unit 1 (Set to Zero for analysis)
Ymin2 = Minimum Output of Unit 2 (Set to Zero for analysis)
α 1 = Initial MW Flow on Monitored Element of Constraint 1
α 2 = Initial MW Flow on Monitored Element of Constraint 2
α 3 = Initial MW Flow on Monitored Element of Constraint 3
α 4 = Initial MW Flow on Monitored Element of Constraint 4
α n = Initial MW Flow on Monitored Element of Constraint n
β 1,1 = DF of Unit 1 on constraint 1
β 1,2 = DF of Unit 1 on constraint 2
β 1, n = DF of Unit 1 on constraint n
β 2,1 = DF of Unit 2 on constraint 1
β 2,2 = DF of Unit 2 on constraint 2
β 2,n = DF of Unit 2 on constraint n
β k,1 = DF of Unit k on constraint 1
β k,n = DF of Unit k on constraint n

If we try to calculate the total constraint flow on Monitored Element of Constraint C1 with two
units Y1 and Y2, then the equation is as follows:

C1 = α1 + Ygen1 * β1,1 + Ygen2 * β2,1 + Ygenk * βk,1
If instead of using two units (Y1 and Y2), we used k units (all the units with provisional and
conditional GIAs) then the above equation would change to the following equation and capture
the DFs of all units (Y1 to Yk) on Constraint C1 as follows:

C1 = α1 + Ygen1 * β1,1 + Ygen2 * β2,1 ……. + Ygenk * βk,1

Similarly, we can extend the same concept for all constraints as follows:

C2 = α2 + Ygen1 * β1,2 + Ygen2 * β2,2 ……. + Ygenk * βk,2
C3 = α3 + Ygen1 * β1,3 + Ygen2 * β2,3 ……. + Ygenk * βk,3
C4 = α4 + Ygen1 * β1,4 + Ygen2 * β2,4 ……. + Ygenk * βk,4
.
.
.
Cn = αn + Ygen1 * β1,n + Ygen2 * β2,n ……. + Ygenk * βk,n


6.2.9.1.4.
Optimization Technique using EXCEL SOLVER
The optimization process needs two sets of critical data:
a. The DFs for each unit for all constraints that are obtained from the results of a MUST
First Contingency Incremental Transfer Capability DC transfer analysis. Therefore, the
MUST output will provide β 1,1, β 2,1 etc. values.
b. The Pmax and Pmin for each generator that has signed a provisional or conditional
GIA. From equations above, we will need Ymax1, Ymin1 etc.

Once the data from 6.2.9.1.4.a and 6.2.9.1.4.b is obtained, then the Excel Solver tool will be used
to calculate the operating limits with the following set of constraints:

Maximize the output of all Units Y1- Yn such that the constrained flows for C1 to Cn are optimized
to the rating of the line. In other words, The Excel Solver will solve and come up with the optimized
value for all Unit outputs within the following constraints:

Maximize Σ Ygen (1 to k) within the following constrained parameter values:

Ymax1>=Ygen1>Ymin1
Ymax2>=Ygen2>Ymin2
Ymaxk>=Ygenk>Ymink
AND

Optimize C1 = Rating of the monitored element of C1
Optimize C2 = Rating of the monitored element of C2
Optimize Cn = Rating of the monitored element of Cn

6.2.9.1.5.
Frequency of these studies
MISO will perform this analysis every planning year quarter and post the results on MISO OASIS
under the following link:

http://www.oasis.oati.com/woa/docs/MISO/MISOdocs/OASIS_report_Page_for_TIAs.mht

6.2.9.2.
Microsoft Excel Help Files Solver Description
Further description of the Excel Solver function can be found at the following link:

https://support.office.com/en-au/article/An-introduction-to-optimization-with-the-Excel-Solver-
tool-1f178a70-8e8d-41c8-8a16-44a97ce99f60

6.2.10. Use of Multi Party Facility Construction Agreement (MPFCA)
A MPFCA will be developed in the event multiple IRs share the responsibility for a common
Network Upgrade or System Protection Facility on the TO’s Transmission System (“Common Use
Upgrade” or “CUU”). A separate MPFCA will be developed for a CUU on each TOs’ Transmission
System. A CUU may consist of multiple Network Upgrades and/or System Protection Facilities.

The Network Upgrades and System Protection Facilities required solely for a single IR on the
direct-connect TO’s Transmission System will continue to be included in the GIA for that IR.
Further, any Network Upgrades or System Protection Facilities that are not a CUU on the
Transmission System of a TO which is not a party to the GIA will continue to be included in the
FCA.

The IC’s GIA will include in Appendix A and Appendix B the facilities that are required under
separate FCA(s) and/or MPFCA(s) and corresponding Milestones that must be completed prior
to commencement of service under the GIA.

ICs with IR that require a CUU will be held responsible to execute and provide irrevocable security
for their respective shares of a MPFCA (or in the case of an unexecuted MPFCA, provide
irrevocable security after acceptance of the unexecuted MPFCA by FERC) in the event that:
i.
A constraint is identified in the DPP SIS, that meets the criteria to require mitigation,
and
ii.
One or more of the following:
a. More than one IR contributes to that constraint, and/or
b. Other IR(s) contribute to a different constraint(s) requiring mitigation before
commencement of their Interconnection Service, and where:
i.
The constraint(s) is resolved by the same upgrade (i.e., CUU); and
ii.
The CUU is determined to be the most prudent upgrade to resolve the
constraint(s) to such a level that the CUU enables the interconnection
of multiple IRs.

6.2.11.   Refunds of Definitive Planning Phase Milestones (M2, M3, M4)

Refunds of Definitive Planning Phase Milestones (M2, M3, M4) – for the Interconnection
Requests for which the application deadline to enter the Definitive Planning Phase is on
or after January 22, 2024

ICs are eligible to receive forty percent (40%) refund of the DPP Entry Milestone (M2) only when
the IR is withdrawn or deemed withdrawn prior to the end of IC Decision Point I. If the IR is
withdrawn any time after the IC Decision Point I, then the DPP Entry Milestone (M2) becomes
one hundred percent (100%) at risk and will be used to fund Study Cost and Network Upgrades
pursuant to Section 7.8 and 7.6.2.1.1 of Attachment X of the GIP.

ICs are eligible to receive one hundred percent (100%) refund of the DPP II Milestone (M3) only
when the IR is withdrawn or deemed withdrawn before the end of IC Decision Point II. If the IR is
withdrawn any time after the ID Decision Point II, then the DPP II Milestone (M3) becomes at risk
and will be used to fund Network Upgrades pursuant to Section 7.8 of Attachment X of the GIP.

ICs are not eligible to receive any portion of the DPP II Milestone (M4) if the IC decides to withdraw
its IR any time after entering the DPP III. The DPP II Milestone (M4) will be used to fund Network
Upgrades pursuant to Section 7.8 of Attachment X of the GIP.

Milestone payments will be refunded in the event the IC withdraws because the total Network
Upgrade cost estimates in the DPP Phase II SIS increased by more than fifty percent (50%) and
more than ten thousand dollars ($10,000) per MW over the DPP Phase I SIS as a result of MISO,
Affected System or TO error.

Milestone payments will be refunded in the event the IC withdraws because the total Network
Upgrade cost estimates in the DPP Phase III SIS increased by more than thirty-five percent (35%)
and more than ten thousand dollars ($10,000) per MW over the DPP Phase II SIS as a result of
MISO, Affected System or TO error.

For the purposes of Automatic Withdrawal Penalty, an error is any of the following confirmed
through documented correspondence with MISO staff before the final study report is posted, for
the phase in which the error was introduced:

•
Incorrect representation of topology in the MISO footprint
•
Incorrect representation of an Interconnection Request in the MISO footprint (or)
•
Incorrect implementation of generation dispatch

The error must also have gone uncorrected and caused an increase to the project’s Network
Upgrade cost.

The error is only relevant for withdrawn Interconnection Requests.

Milestone payments less any Automatic Withdrawal Penalty amounts applied pursuant to Section
7.6.2.1.1 of the Attachment X, will also be refunded in the event the IC withdraws and the total
Network Upgrade cost estimates in the Facilities Study increased by more than thirty-five percent
(35%) and more than ten thousand dollars ($10,000) per MW over the Network Upgrade cost
estimates in the DPP Phase III Interconnection SIS.

Milestone payments less any Automatic Withdrawal Penalty amounts applied pursuant to
Section 7.6.2.1.1 of the Attachment X, will also be refunded in the event the IC withdraws within
the later of five (5) Business Days or at the end of an IC Decision Point, if applicable, of results
indicating designated increases in estimated upgrade costs across the following intervals:
1. DPP Phase I to DPP Phase II
a. An increase in the combined MISO Network Upgrade costs from Phase I to
Phase II of at least fifty percent (50%) and more than ten thousand dollars
($10,000) per MW from the preliminary SIS to the Revised SIS; or
2. DPP Phase II to DPP Phase III

a. An increase in combined MISO Network Upgrade and Affected Systems costs
from Phase II to Phase III of at least thirty-five percent (35%) and more than
fifteen thousand dollars ($15,000) per MW from the Revised SIS to any Final
SIS.
Refunds of Definitive Planning Phase Milestones (M2, M3, M4) – for the Interconnection
Requests for which the application deadline to enter the Definitive Planning Phase is
before January 22, 2024

ICs are eligible to receive fifty percent (50%) refund of the DPP Entry Milestone (M2) only when
the IR is withdrawn or deemed withdrawn prior to the end of IC Decision Point I. If the IR is
withdrawn any time after the IC Decision Point I, then the DPP Entry Milestone (M2) becomes
one hundred percent (100%) at risk and will be used to fund Study Cost pursuant to Section 7.8
of Attachment X of the GIP.

ICs are eligible to receive one hundred percent (100%) refund of the DPP II Milestone (M3) only
when the IR is withdrawn or deemed withdrawn before the end of IC Decision Point II. If the IR is
withdrawn any time after the ID Decision Point II, then the DPP II Milestone (M3) becomes at risk
and will be used to fund Network Upgrades pursuant to Section 7.8 of Attachment X of the GIP.

ICs are not eligible to receive any portion of the DPP II Milestone (M4) if the IC decides to withdraw
its IR any time after entering the DPP III. The DPP II Milestone (M4) will be used to fund Network
Upgrades pursuant to Section 7.8 of Attachment X of the GIP.

Milestone payments will be refunded in the event the IC withdraws because the total Network
Upgrade cost estimates in the DPP Phase III SIS increased by more than twenty five percent
(25%) and more than ten thousand dollars ($10,000) per MW over the DPP Phase II SIS as a
result of MISO, Affected System or TO error.

Milestone payments will also be refunded in the event the IC withdraws and the total Network
Upgrade cost estimates in the Facilities Study increased by more than twenty five percent (25%)
and more than ten thousand dollars ($10,000) per MW over the Network Upgrade cost estimates
in the DPP Phase III Interconnection SIS.

Milestone payments will also be refunded in the event the IC withdraws within the later of five
(5) Business Days or at the end of an IC Decision Point, if applicable, of results indicating
designated increases in estimated upgrade costs across the following intervals:
1. DPP Phase I to DPP Phase II

a. An increase in the MISO Network Upgrade costs from Phase I to Phase II of at
least fifty percent (50%) and more than ten thousand dollars ($10,000) per MW
from the preliminary SIS to the Revised SIS;

b. Affected System upgrade costs on transmission systems other than the MISO
Transmission System of more than ten thousand dollars ($10,000) per MW.

2. DPP Phase II to DPP Phase III
a. An increase in MISO Network Upgrade costs from Phase II to Phase III of at
least thirty-five percent (35%) and more than fifteen thousand dollars ($15,000)
per MW from the Revised SIS to any Final SIS;

b. An increase in Affected System upgrade costs on transmission systems other
than the MISO Transmission System of forty percent (40%) and more than
fifteen thousand dollars ($15,000) per MW


          3. DPP Phase I to DPP Phase III

                      a. An increase in MISO Network Upgrade costs of fifty percent (50%) and more
                            than twenty thousand dollars ($20,000) per MW from the Preliminary SIS to
                            any DPP Phase III SIS.


6.3. Coordination of studies between PJM and MISO
In accordance with Section 9.3.3 of the MISO-PJM Joint Operating Agreement (“JOA”), MISO
and PJM shall conduct Interconnection Studies, as necessary, to determine the impacts of IRs on
each other’s transmission system, which will be treated as an Affected System. This joint
coordination of Interconnection Studies will be in addition to the existing Interconnection Studies
that MISO and PJM already perform to evaluate the impacts of their respective queues on their
own transmission system and will be subject to the guidelines laid out in the MISO-PJM JOA.

The Transmission reinforcement and the study criteria used in the Coordinated Interconnection
Studies will honor and incorporate provisions as outlined in the PJM and MISO Business Practices
Manuals and their respective Tariffs.

When MISO and PJM perform any Coordinated Interconnection Study, the PJM and PJM TO
study and reinforcement criteria will apply to PJM transmission facilities and the MISO and MISO
TO study and reinforcement criteria will apply to MISO transmission facilities. For all tie lines
between MISO and PJM, the reinforcement criteria and cost allocation rules of the region that
identified the constraint criteria violation will be applied.

Coordination timing, as prescribed below, shall be based on the current MISO and PJM study
cycles, and will be adjusted if there are changes to the study cycle timelines in the future.

6.3.1.
Study of PJM Interconnection Request Impacts on MISO
Transmission
During the course of its interconnection feasibility studies, PJM shall monitor the MISO
transmission system and provide to MISO the draft results of the potential impacts to the MISO
transmission system. This monitoring will include an examination of the potential for projects to
impact the MISO system by determining whether the project under study has a ≥ 3 percent
distribution factor on MISO facilities that operate below 500 kV or ≥ 10 percent distribution factor
on MISO facilities that operate at or above 500 kV under system intact conditions.

Following the completion of the PJM Feasibility Study and after the execution of the PJM SIS
Agreement by the customer, PJM shall forward to MISO, at a minimum of twice per year (March
15 and September 15), information necessary for MISO and the MISO TOs to study the impact
of the PJM IRs on the MISO transmission system.

MISO and the MISO TOs shall study the impact of the PJM Interconnection on the MISO
transmission system and provide draft results to PJM by:
•
February 1 for PJM IRs provided to MISO on or before September 15 of the previous
year,
•
August 1 for PJM IRs provided to MISO on or before March 15 of the same year.
During the course of MISO’s affected system interconnection study for PJM interconnection
requests, MISO shall apply Energy Resource Interconnection Service (ERIS) criteria to all of
PJM’s interconnection request(s).  These impacts will be studied using methodology and criteria
specified in Section 0 of the MISO BPM and may include thermal analysis and other analysis as
necessary. These impacts identified by MISO shall include a description of the required system
reinforcement(s), an estimated planning level cost and construction schedule estimates of the
system reinforcement(s). The results received from MISO, including any required transmission
system reinforcements, shall be included in the PJM System Impact Study or Facilities Study
report consistent with the PJM OATT. At times PJM may identify to MISO the need to perform
studies associated with an IR other than the times identified above. MISO shall endeavor to study
these requests at the earliest time that is feasible, but not later than the times as specified above
(commencing after March 15 and September 15).

In the event of project withdrawals in the PJM queue, MISO may perform additional reliability
analysis during the PJM Facilities Study phase and revise the affected system study results that
were provided during the PJM SIS phase.

If MISO identifies required Network Upgrades on the MISO transmission system, due to a PJM
IR, the PJM IC(s) shall be required to follow all provisions, delineated under Attachment X of the
MISO tariff, related to Facilities Study funding and appropriate Network Upgrade FCA.

Cost allocation for required Network Upgrades on the MISO transmission system, for PJM
Interconnection projects, shall be governed by and subject to MISO Tariff and BPMs.

6.3.2.
Study of MISO Interconnection Request Impacts on PJM
Transmission
After each MISO DPP cycle application deadline and at least thirty (30) days prior to the
commencement of the DPP Phase I of the DPP for such cycle, MISO shall perform screening
analysis on all Interconnection Requests in such study cycle to monitor for impacts to the PJM
transmission system and provide to PJM the draft results of the potential impacts to the PJM
transmission system. This monitoring will include an examination of the potential projects to
impact the PJM system through determination if the project under study has a ≥3 percent
distribution factor or ≥ 5 MW impact or ≥ 1 percent of facility rating on any PJM facilities under
normal and contingency conditions.

No later than five (5) Business Days after the commencement of the MISO DPP Phase I study,
MISO shall forward to PJM information necessary for PJM and the PJM TOs to study the impact
on the PJM transmission system of the MISO Interconnection Request(s) in such cycle that
entered DPP Phase I. PJM and the PJM TOs may study the impact of the MISO Interconnection
Request(s) on the PJM transmission system and provide any available preliminary results to
MISO within 100 days following commencement of DPP Phase I.

Prior to commencing the MISO DPP Phase II study, MISO shall forward to PJM the latest available
information necessary for PJM and the PJM TOs to study the impact on the PJM transmission
system of the MISO Interconnection Request(s) included in such study. PJM and the PJM TOs
shall study the impact of the MISO Interconnection Request(s) on the PJM transmission system
and provide the study results to MISO no later than 30 days prior to the completion of DPP Phase
II.

Prior to commencing the MISO DPP Phase III study, MISO shall forward to PJM the latest
available information necessary for PJM and the PJM TOs to study the impact on the PJM
transmission system of the MISO Interconnection Request(s). PJM and the PJM TOs may study
the impact of the MISO Interconnection Request(s) on the PJM transmission system and provide
the study results to MISO no later than 30 days prior to the completion of DPP Phase III.

During the course of PJM’s affected interconnection study for MISO interconnection projects, PJM
shall model all MISO interconnection projects that have requested Network Resource
Interconnection Service (NRIS) under the MISO OATT as a Capacity Resource under the PJM
OATT and all MISO interconnection projects that have requested ERIS under the MISO OATT as
an Energy Resource under the PJM OATT. All projects will be modeled and studied using the
criteria and methodology described in PJM Manual 14B.
These impacts identified by PJM shall include a description of the required reinforcements on
PJM’s transmission system, an estimated planning level cost and construction schedule estimates
of the system reinforcement. The results received from PJM, including any required transmission
system reinforcements, shall be included in the MISO System Impact Study report.  At times MISO
may identify to PJM the need to perform studies associated with an Interconnection other than
the times identified above. PJM shall endeavor to study these requests at the earliest time that is
feasible.

If PJM identifies required Network Upgrades on the PJM transmission system, due to a MISO R,
then the MISO IC(s) shall be required to follow all provisions delineated under the PJM Tariff
related to Facilities Study funding and appropriate Network Upgrade FCA obligations.

Cost allocation for Network Upgrades necessary on the PJM transmission system due to MISO
Interconnection projects shall be governed by and subject to the PJM Tariff and related Manuals.

6.3.3.
Coordination of Projects with Provisional/Conditional GIAs
If a generation interconnection project is conditional upon Network Upgrades on the Affected
System and comes in service prior to those Network Upgrades being completed, that project’s
output will be subject to limitations in accordance with the applicable tariff of the Affected System.

6.4. Coordination of Studies between SPP and MISO
In accordance with Section 9.4 of the MISO-SPP Joint Operating Agreement (“JOA”), MISO and
SPP shall conduct Interconnection Studies, as necessary, to determine the impacts of IRs on
each other’s transmission system which will be treated as an affected system. This joint
coordination of Interconnection Studies will be in addition to the existing Interconnection Studies
that SPP and MISO already perform to evaluate the impacts of their respective queues on their
own transmission system and will be subject to the guidelines laid out in the MISO-SPP JOA.

The transmission reinforcement and the study criteria used in the coordinated interconnection
studies will honor and incorporate provisions as outlined in the SPP and MISO Business Practices
Manuals, study procedures, and their respective Tariffs.

6.4.1.
Requirements Applicable to All Clusters, Interconnection Customers
and Interconnection Requests

The requirements listed in Section 9.4.1 of MISO-SPP JOA shall apply to all clusters,
interconnection customers, and interconnection requests regardless of whether such clusters,
interconnection customers, or interconnection requests are included in the Joint Targeted
Interconnection Queue (“JTIQ”) Screening Group:
 (a) Consistent with the data exchange provisions of this Agreement, the Parties will
exchange modeling data as necessary for the study and coordination of interconnection requests.
This will include associated updates to modeling data as necessary to reflect the other Party’s
relevant queue requests, contingency elements, monitored elements, planned upgrades, and
other data as may be required.
  (b)  The identification of all impacts on the Parties’ transmission systems shall include a
description of the required Network Upgrade(s), and corresponding planning level cost estimates
and construction schedule estimates.
 (c) Construction of any Network Upgrades on the Affected System will be subject to the
terms of the impacted Party’s OATT and agreement among owners of transmission facilities
subject to the control of the impacted Party and will be consistent with applicable federal, state or
provincial regulatory policy.
 (d)  In the event that Network Upgrades are required on the potentially impacted Party’s
system, then such Network Upgrades shall be documented as a condition for full Interconnection
Service in the interconnection agreement executed by the direct connect system. Additionally, the
Parties will mutually agree on milestones with respect to the Network Upgrade construction and
the amount of service that can commence after each milestone.
  (e) Each Party will maintain a separate interconnection queue. The Parties will maintain
a listing of interconnection requests for all interconnection projects that have been identified as
potentially impacting the systems of the other Party. This information will be publicly posted on
the Parties’ respective websites

6.4.2.
Requirements for Interconnection Requests Included in JTIQ
Participation Group and/or for Expanded Scope Analysis

The rules and procedures contained in MISO-SPP JOA Section 9.4.2 shall apply to
interconnection customers with interconnection requests, including MISO DPP, MISO ERAS,
SPP DISIS, or SPP ERAS, that have been designated for inclusion in a JTIQ Participation Group
and/or for the Expanded Scope Analysis identified in Section 9.4.2.d.iv.a. To the extent any
provision in Section 9.4 and related subsections conflicts with the provisions pursuant to Section

9.4.2 as applicable to JTIQ Upgrades, the provisions pursuant to Section 9.4.2 shall govern for
JTIQ Upgrades:
(a) Adoption of JTIQ Portfolio
(b) Cost allocation for JTIQ Portfolios
(c) Responsibility to Construct
(d) Identification of JTIQ Screening Group, JTIQ Participation Group and JTIQ
Commitment Group
(e) Closing Subscription to the JTIQ Portfolio; Addressing Oversubscription and
Undersubscription
(f) Cost Recovery from the JTIQ Commitment Group and Backstop Funding
(g) Calculation, Collection and Distribution of JTIQ Generator Charge (h) Security
requirements

6.4.3.
Coordination Procedure for Interconnection Requests Not Included
in a JTIQ Participation Group or Expanded Scope Study

The rules and procedures contained in MISO-SPP JOA Section 9.4.3 shall apply to the analysis
of interconnection requests, including MISO DPP, MISO ERAS, SPP DISIS, or SPP ERAS, that
have not been designated for inclusion in either a JTIQ Participation Group or an Expanded Scope
Study
•
Relative Queue Position for interconnection requests in the MISO or SPP
interconnection queues, other than for MISO ERAS or SPP ERAS interconnection
requests
•
Affected System Study Criteria, Procedure, Cost allocation
•
Communication of Potential Impacts to the Affected System
•
Notification to MISO of Potential Impacts Identified from SPP DISIS and ERAS
Studies
•
Notification to SPP of Potential Impacts Identified from MISO DPP and ERAS
Studies
•
Requirements of Facility Study Agreement
•
Study Funds
•
Documentation of Affected System Network Upgrades in the Host System Impact
Study
•
Documentation of Affected System Network Upgrades in the Applicable
Interconnection Agreements
•
Requirements to Minimize Cost of Coordination Studies

Table 6.4-1 provides a high-level summary of Interconnection Study Coordination between MISO
and SPP as per requirements in Section 9.3 and 9.4 in the MISO-SPP JOA.

Table 6.4-1 Coordination of MISO/SPP Interconnection Requests

6.4.4 Coordination of Projects with Provisional/Conditional GIAs

If a generation interconnection project is conditional upon Network Upgrades on the Affected
System and comes in service prior to those Network Upgrades being completed, that project’s
output will be subject to limitations in accordance with that respective RTO’s tariff.

6.4.4.1.
Limitations on SPP Generators with Impacts on the MISO System
SPP Generation Interconnection Projects that come into service prior to completion of required
Network Upgrades on the MISO transmission system will be subject to the MISO Annual ERIS
and Quarterly Operating Limit processes, as outlined in Section 6.6 of this BPM and the MISO
Tariff in Attachment X Section 11.5, until required Network Upgrades on the MISO transmission
have been completed. MISO will coordinate project output limitations with SPP on a quarterly
basis, and MISO will provide SPP with the list of conditions that will be added to SPP IC’s
Interconnection Service agreement.

6.4.4.2.
Limitations on MISO Generators with Impacts on the SPP System
MISO Generation Interconnection projects that come into service prior to completion of required
Network Upgrades on the SPP transmission system will be subject to the MISO Annual ERIS and
Quarterly Operating Limit processes, with input from SPP’s Affected System study process.  .
SPP will coordinate thermal constraints and associated limits with MISO on a quarterly basis or
more often as events occur, and SPP will provide MISO the list of conditions that will be added to
MISO Generator Interconnection Agreement.

Request
JTIQ
Participation
Group?
Subject to Expanded
Scope Analysis?
Require
Regular
MISO/SPP AFS?
MISO DPP/MISO ERAS
West, Central, ATC, ITC
regions
Yes
Yes
No
No
Yes
No
MISO DPP/MISO ERAS
South
Yes
Yes
No
No
No
Yes
SPP DISIS/ SPP ERAS
(Group 1,2,3)
Yes
Yes
No
No
Yes
No
SPP DISIS/ SPP ERAS
(Group 4,5)
Yes
Yes
No
No
No
Yes

6.4.4.3.
Limitations on PJM Generators with Impacts on the MISO System
PJM Generation Interconnection Projects that come into service prior to completion of required
Network Upgrades on the MISO transmission system will be subject to the MISO Quarterly
Operating Limit process, as outlined in the MISO Tariff in Attachment X Section 11.5 and in the
MISO Transmission Access Planning Provisional Interconnection Agreement Limit Methodology
whitepaper, until required Network Upgrades on the MISO transmission system have been
completed. MISO will coordinate project output limitations with PJM on a quarterly basis, and
MISO will provide PJM with the list of conditions that will be added to PJM IC’s Interconnection
Service agreement.

6.4.4.4.
Limitations on MISO Generators with Impacts on the PJM System
MISO Generation Interconnection projects that come into service prior to completion of required
Network Upgrades on the PJM transmission system will be subject to PJM’s yearly process until
required Network Upgrades on the PJM transmission system have been completed. PJM updates
the output limits on all Interconnection Service agreements on a yearly basis, at a minimum, to
account for changing transmission and generation assumptions. Any significant changes to the
assumptions of the study may be reviewed on a more frequent basis. PJM will coordinate project
output limitations with MISO on a yearly basis, and PJM will provide MISO with the list of
conditions that will be added to MISO Generator Interconnection Agreement.

6.5 Coordination of Studies between Manitoba Hydro (MH), Minnkota
Power Cooperative (MPC), and MISO

6.5.1.
Application of Governing Agreements

6.5.1.1.
Governing Agreement for MPC and MISO Coordination
This coordination procedure is established between MPC and MISO pursuant to sections 9.1 and
14.1 of the MISO-MPC Coordination Agreement.

6.5.1.2.
Governing Agreement for MH and MISO Coordination
This coordination procedure is established between MH and MISO pursuant to section 5.4 of the
MISO-MH Coordination Agreement.

6.5.1.3.
Governing Agreement for MPC and MH Coordination
This coordination procedure is established between MPC and MH pursuant to sections 9.011,
9.02, and 9.022 of the Interconnection, Facilities and Coordinating Agreement respecting
Ridgeway-Shannon 230 kV Interconnection.

6.5.2
Purpose
The purpose of this coordination procedure is to coordinate Generation IRs and Long-Term Firm
Transmission Service Requests where one of the three parties may be an Affected System. Each
party will implement this procedure through Tariff and/or Business Practices under each party’s
respective tariff(s).

6.5.3
Definitions
•
Affected System: a non-Host TSP whose transmission system may be reasonably expected
to experience a non-trivial loading impact due to a TSR or GIR on a Host TSP’s transmission
system.
•
Affected System Upgrades: upgrades required to the Confirmed Affected System
transmission system to accommodate the Host TSP GIR or TSR. The need for the Affected
System Upgrade will be identified in the impact study and further defined in the Affected
System facilities study.
•
Business Practices: a (set of) document(s) that implement certain obligations of the
respective party and its tariff customer.
•
Confirmed Affected System: An Affected System that has been confirmed through either
the Host TSP or the Affected System impact analysis that the Affected System has an
impacted facility due to a TSR or GIR on a Host TSP’s transmission system as shown in the
Host TSP impact study report
•
Generation Interconnection Request or GIR: a request to interconnect or modify generation
under the respective TSP’s policies and procedures (MISO’s tariff Attachment X (Generator
Interconnection Procedures (GIP)), MPC’s Large Generator Interconnection Procedures
(LGIP) or Small Generator Interconnection Procedures (SGIP), or MH’s Open Access
Interconnection Tariff (OAIT))
•
Generator Interconnection Agreement or GIA: an agreement documenting the terms of
interconnection service between a TSP and its customer.
•
Host TSP: MH, MPC, or MISO that receives the GIR or TSR
•
Impact Study Agreement: the agreements under each party’s respective policies and
procedures to evaluate the impact of the TSR or GIR
•
Long Term Firm Transmission Service Request (TSR): a request for long term firm
transmission service across the TSP’s transmission system under the respective party’s tariff
(MISO’s tariff, MPC’s Open Access Transmission Tariff (OATT), or MH’s OATT)
•
MISO Definitive Planning Phase or DPP: the final impact study phase for MISO GIRs as
defined by the Business Practices under MISO’s Tariff.
•
MISO M2 Milestone: the MISO DPP entry milestone as defined by the Business Practices
under MISO’s Tariff.

•
Neighbouring TSP(s): MH, MPC, and/or MISO that does not receive the GIR or TSR.
General reference to any or all of the parties to this coordination language.
•
Network Upgrade: upgrade required on the Host TSP transmission system to accommodate
the GIR or TSR as defined by the parties’ respective tariffs, policies, or procedures.
•
POR/POD: Point of Receipt/Point of Delivery as defined by each party’s respective tariffs.
•
Remedial Action Scheme: as defined by NERC standards.

Transmission Service Provider or TSP – as defined by NERC standards.

6.5.4.
Scope
This section defines the GIRs and TSRs that are deemed in scope for this procedure. A
GIR or TSR that is deemed in scope will be subject to the coordination procedures
below. If the GIR or TSR is not deemed in scope, it is not subject to the coordination
procedures below.

6.5.4.1
Large Generator Interconnections
A GIR is deemed in scope for this coordination procedure as follows:
i.
All MISO North GIR for MISO
ii.
All GIR for MPC
iii.
All GIR for MH

For any GIR that falls within this scope, the Neighbouring TSPs will be considered Affected
Systems.

MISO North refers generally to the northern part of MISO, which is subject to change as members
join or leave MISO. The red section in the picture20 below captures the in-scope area for MISO at
the time the agreement was executed.


20
From
MTEP
2014
-
https://www.misoenergy.org/planning/transmission-studies-and-reports/#nt=%2Freport-study-
analysistype%3AMTEP%2Fmtepdoctype%3AMTEP%20Report%2Fmtepreportyear%3APrevious%20MTEP%20Reports&t=10&p=0&s=Fil
eName&sd=desc

Figure 0-2 MISO Planning Regions

6.5.4.2.
Small Generator Interconnections
If it is determined by the Host TSP that a GIR is potentially eligible for accelerated processing
under the Host TSP’s interconnection procedures due to its small size, the GIR will be deemed in
scope for this coordination procedure as follows:
•
All GIR for MISO interconnecting in the following LBAs: GRE, MDU, MP, NSP, OTP
•
All GIR for MPC

MH does not differentiate between small generator and large generator interconnections and
therefore does not offer accelerated processing for small generator interconnections.

6.5.5.
Procedure

6.5.5.1.
Generation Interconnection Requests
MISO, MH, and MPC have agreed to the following process by which Generator IR studies are
conducted to determine the impacts of Generator IRs on each other’s transmission systems.
Coordination with Affected Systems is required by the parties’ respective policies and procedures.
This joint coordination of Generator IR studies serves to clarify the process by which that
coordination is conducted for MISO, MH, and MPC.

Process diagrams are included to provide clarity. If a conflict arises between the process diagram
and the text in this procedure, the text shall rule.

6.5.5.1.1.
Queue Priority and Cost Allocation
For the purposes of performing impact studies, all parties will model higher queued and
concurrently queued projects. Position in the queue is determined by:
•
The date that a valid GIR is received under the MH tariff.
o For a group study conducted under the MH OAIT, the queue position of the
group relative to MISO and MPC projects will be the date that the last valid GIR
in the group study was received by MH.
•
The date that a valid GIR is received under the MPC LGIP or SGIP
o For a cluster study conducted under the MPC LGIP, the queue position of the
cluster relative to MISO and MH projects will be the date that the last valid GIR
in the cluster was received by MPC.
•
The MISO M2 Milestone payment submission deadline per the MISO tariff.

MISO projects will not in any event be considered to have equal queue priority to an MH or MPC
project, due to the fact that the MISO (M2) Milestone deadline is at a specific point in time. An MH
or MPC Impact Study Agreement that is signed on the MISO (M2) Milestone deadline will have
higher queue priority than the MISO project. An MH or MPC Impact Study Agreement that is

signed the day after the MISO (M2) Milestone deadline will have lower queue priority than the
MISO project.

MPC and MH projects will have the same queue priority if the Impact Study Agreements are
signed on the same day. In this case, they will be treated as concurrent projects for cost allocation
on common Network Upgrades and Affected System Upgrades.

Projects with a completed impact study or a GIA that was executed prior to the implementation of
this jointly coordinated language between MH, MPC, and MISO will be treated as higher queued
generators in future interconnection studies.

The highest queued project (or group of projects in a group study) driving the need for an upgrade
shall pay for the upgrades required to mitigate its impact on the transmission system, consistent
with cost causation principles, unless the parties agree on another cost allocation that results in
a more desirable outcome for the customers. The Neighboring TSP will provide cost of upgrades
required on its system to the Host TSP for cost allocation amongst the generator interconnection
projects using Host TSP’s cost allocation methodology. In the case of concurrent MH and MPC
projects, if projects are deemed to require the same upgrade, costs will be allocated pro rata
based on each project’s respective impact on the constrained element unless otherwise agreed
to by MH and MPC.

6.5.5.1.2.
Notice
The Host TSP will provide notice of GIRs identified in section 0 to the Neighboring TSPs:
•
When a valid GIR is received by MPC;
•
When a valid GIR is received by MH; and
•
When the MISO M2 Milestone deadline has passed for MISO.

The Host TSP will send an email with details of the associated GIR project so that the Neighboring
TSP can begin including the project in their models. The Host TSP will include the Neighboring
TSPs in the ad-hoc study group for a Host TSP GIR impact study.

The Host TSP will also provide a similar notice to the Neighboring TSPs following a qualified
change or withdrawal of a GIR identified in section 6.5.4.
6.5.5.1.3.
Impact Study Obligations
The Host TSP will monitor impacts on the Neighboring TSP’s transmission systems in all Host
TSP impact studies and provide the results to the Neighboring TSP’s.

Results and any associated mitigations on the Host TSP’s transmission system will be
provided at the earliest possible date to allow for the Neighboring TSPs to consider the
impacts identified on their own transmission systems.

When the Host TSP performs the impact study, the Host TSP will use reasonable efforts to
monitor the affected system and:
•
The MISO and the MISO TO study and reinforcement criteria will apply to the
monitoring of MISO transmission facilities;
•
The MPC study and reinforcement criteria will apply to the monitoring of MPC
transmission facilities; and
•
The MH study and reinforcement criteria will apply to the monitoring of MH
transmission facilities.

These potential impacts will be included in the Host TSP impact study report. The Host TSP will
provide the Affected Systems the opportunity to validate the impacts on their transmission
systems and identify mitigations.

Additionally, the Neighboring TSP’s can each choose to study the impacts of the Host TSP GIR
on their own transmission systems and send results to the Host TSP for inclusion in the final
impact study report. The Host TSP will provide the necessary information and models so that
Neighboring TSP’s can perform these impact studies. The Host TSP will allow the Neighboring
TSP the same amount of time to complete affected system studies as the Host TSP has
scheduled for its own study. The Host TSP may request results slightly in advance of its own
deadline in order to incorporate the Neighboring TSP’s results into its own report. The Host TSP
will allow the Neighboring TSP’s extra time if requested and if the additional delay does not hinder
timely completion of the Host TSP’s impact study.

If the Affected System’s policies allow for the sharing of study models, an IC can apply to obtain
the study models from the Affected System by executing the required confidentiality agreements.

The Host TSP shall include in the Host TSP impact study report the impacts on the Affected
System based on Affected System criteria. Any changes to the Affected System Criteria shall not
be enforceable once the Affected System study has started. These impacts shall include:
•
The minimum amount of interconnection service that can be granted without Affected
System Upgrades,
•
A description of the required system reinforcements,
•
A planning level cost estimate, and
•
Preliminary estimate of the in-service date of the system reinforcement.

The Host TSP will promptly share impact study reports with the Affected Systems upon
completion.

6.5.5.1.4.
Mitigating Host TSP GIR Impacts on the Confirmed
Affected System’s Transmission System
If the impact study confirms a constraint to interconnection service on an Affected System’s
transmission system, the Host TSP will require the customer to contact the Confirmed Affected
System and make arrangements with the Confirmed Affected System to identify and construct
facilities for mitigation of impacts. For required Affected System Upgrades on the Confirmed
Affected System due to a Host TSP GIR, the Host TSP will require the IC(s) to follow all provisions
delineated under the Affected System policies, procedures, and Business Practices. Required
arrangements include but are not limited to signing the facilities study agreement and signing the
Confirmed Affected System upgrades agreement to construct the mitigations identified in the
Confirmed Affected System facilities study.

The Host TSP and Confirmed Affected System will promptly share facility study reports with each
other upon completion.

If generation interconnection projects are granted interconnection service by the Host TSP prior
to completion of required Affected System Upgrades on the Confirmed Affected System,
commercial operation shall be limited up to the amount at which there are no transmission
constraints identified by the studies on the Confirmed Affected System(s) transmission system.
The study to determine limitation is coordinated between the Host TSP and the Confirmed
Affected System TSP. If one exists, the Affected System will provide operating limitation policies
to the IC upon request.
6.5.5.1.5.
Special Provisions for Accelerated Processing
For generators that are eligible for accelerated processing and are deemed to be in scope for this
coordination procedure, the parties agree to the following special provisions:
•
Notice will be provided to the Neighbouring TSPs upon receipt of a valid GIR.
•
The Host TSP will inform the Neighbouring TSPs of their study schedule deadlines
and request that the Neighbouring TSPs use good faith efforts to accommodate the
Host TSP’s accelerated schedule if the Neighbouring TSP performs an Affected
System study.
•
In the event that a Neighbouring TSP is not able to complete an Affected System study
in time to meet the Host TSP’s study schedule, the Host TSP will continue in
accordance with its posted procedures, making reasonable efforts to accommodate a
late submission by the Neighbouring TSP.

If a GIR that was potentially eligible for accelerated processing is later required to complete the
standard interconnection process, the normal provisions of the agreement will apply.

GIR Coordination – Affected System
Affected System Process
Host GIR Process
Customer
submits IR
Host TSP sends
Notice to Affected
Systems
Affected System
decides if a sensitivity
study is done?
Host completes
the Impact Study
monitoring Host
TSP System and
Affected Systems
Host TSP finalizes impact
study and includes impacts
on Host and Neighboring
TSP from Host and Affected
System impact studies
Are there
impacts in
Affected
System?
Customer
signs facilities
study
agreement
with Host
TSP
Host TSP and
customer sign
facility
construction
agreement
Host TSP
grants service
at level that all
impacts are
mitigated
Confirmed
Affected System
completes
Affected System
facilities study and
issues to customer
and Host TSP
Customer and
Confirmed
Affected System
sign Affected
System
construction
agreement
Are impacts
mitigated in time
for service?
Confirmed Affected System notifies
Host TSP that no restriction needs to
be imposed on service
Confirmed Affected
System notifies
Host TSP of
restriction on
service to be
imposed until
impacts are
mitigated
Affected System
assesses impacts
and proposes
mitigations
Yes
Yes
Yes
No
Affected System Relies
on Host TSP for
monitoring
No
Host TSP
Receives GIR
Host TSP issues
impact study to
customer and
Neighboring TSP
systems
Customer works with
Confirmed Affected
System to sign Affected
System facilities study
agreement
Host TSP issues
facilities study to
customer and
Confirmed
Affected Systems
Affected
System
Coordination
not required
No
Host identifies
impacts in
Affected
System
Confirmed
Affected
System issues
study to Host
TSP and
Customer

6.5.5.2.

Compensation for Affected System Analysis (Applicable to
MPC and MISO Only)
The IC will be responsible for the costs incurred by the Neighbouring TSP for performing affected
system analysis associated with SISs with the help of engineering consultants. A Host TSP will
reimburse the Neighbouring TSP using IC’s study deposit funds upon receipt of an invoice from
the Neighbouring TSP. Only the direct costs of the engineering consultants will be included in the
invoice.

6.6
Annual ERIS Evaluation and Annual Interim Deliverability Study
6.6.1 Scope
For all permanent GIAs with conditions and Provisional GIAs, an Annual ERIS evaluation will be
performed which will identify the maximum level of injection available for the next Resource
Adequacy Planning Year. Further, for all permanent GIAs with conditional ERIS that will
eventually convert to ERIS and NRIS, an Annual Interim Deliverability analysis will be performed
which will identify the maximum level of conditional NRIS available for the next Resource
Adequacy Planning Year, up to the level of eventual NRIS. If a project has explicit conditions
associated with MTEP Appendix A projects, listed in their existing GIA, the Annual ERIS and
Annual Interim Deliverability Studies will be applicable from the time of their Commercial
Operation Date (as declared under BPM-015 Section 7.7 requirements) until those explicit
conditions are met.

6.6.2.
Eligibility and Timing of Studies
The Annual ERIS and Annual Interim Deliverability study for the next Planning Year will be
completed by October 31st of every calendar year with results posted on the MISO Extranet and
documented in the MISO Interconnection Service Workbook.

The Annual ERIS and Annual Interim Deliverability Analysis for the next Planning Year will include
only those projects with Generator Interconnection Agreements that have been executed by April
15th of the study calendar year. In addition, all generators that are subject to the Annual studies
must be online during the Planning Year being analyzed.  MISO will notify those eligible projects
at the beginning of the study process.



6.6.3.
Annual ERIS Evaluation

The maximum amount of injection available for the studies generator will be identified for the next
Planning Year.

6.6.3.1.
Methodology
The Annual ERIS evaluation will include the following suite of reliability analyses that will be
carried out on both the Summer Peak and Shoulder Peak cases:
i.
Thermal Analysis,
ii.
Steady State Voltage Analysis (to be completed per Transmission Owner request if
voltage constraints were identified in the DPP studies and the mitigation projects are
not yet in place),
iii.
Transient Stability Analysis (to be completed per Transmission Owner request if
stability constraints were identified in the DPP studies and the mitigation projects are
not yet in place)

The constraint criteria for the above analyses will be consistent with the Generator SIS criteria as
laid out in Sections 6.1.1.1.6, 6.1.1.2 and 6.1.2.4. This study will not identify any Network
Upgrades on the Transmission System. The injection limit from this analysis will be determined
on a pro rata basis based on the nameplate of the generators under evaluation. A constraint
should not be considered as a limit if the LODF (Line Outage Distribution Factor) between the
overloaded element and the unfinished contingent facility from the project’s GIA is less than 20%.
This LODF screening does not apply if the overloaded element in this analysis, or the unfinished
contingent facility, is directly connected at the generator’s POI.

6.6.3.2.
Base Case Assumptions
The Summer Peak and Shoulder Peak Base Cases for the Annual Interim ERIS evaluation will
be reflective of the Generation and Transmission System expected to be in service at the start of
the Planning Year. The individual cases for the following years will be reflective of the
Transmission and Generation that is expected to be in service at the start of those individual
Planning Years.

6.6.3.3.
Load Levels and Generation Dispatch
The Summer Peak and Shoulder Peak case Load Levels and Generation Dispatch will be
consistent with Load Level and Dispatch assumptions used for the respective MTEP Cases as
per Section 3.3 of MISO Transmission Planning BPM 020. The Generator IRs under consideration
for Annual Interim ERIS evaluation would be dispatched consistent with the existing Section
6.1.1.1.1.1.

6.6.4.
Annual Interim Deliverability Study
The maximum amount of conditional NRIS available, for the next Planning Year, will be identified.
In addition, the Annual conditional NRIS value will be capped at the lower of a) Annual ERIS value
or b) Annual Interim Deliverability study NRIS value.

6.6.4.1.
Methodology
The Interim Deliverability Study will follow the MISO deliverability methodology as documented in
Appendix C of this BPM.

The Interim Deliverability Analysis will be performed on the Summer Peak Case used for the
Annual ERIS evaluation analysis.  A constraint should not be considered as a limit if the LODF
(Line Outage Distribution Factor) between the overloaded element and the unfinished contingent
facility from the project’s GIA is less than 20%.  This LODF screening does not apply if the
overloaded element in this analysis, or the unfinished contingent facility, is directly connected at
the generator’s POI.

6.6.5.
Exit from Annual ERIS and Annual Interim Deliverability Studies
Any Interconnection Project with explicit conditionality associated with MTEP Appendix A projects,
listed in their existing GIA based on the A10 process (Section 6.2.4), will exit the Annual ERIS
and Annual Interim Deliverability Studies when those explicit conditions have been met and when
the obligations to direct assigned upgrades to the GI project(s) have been met.  For purposes of
this section, the following situations shall not prevent the exit from the Annual ERIS and Annual
Interim Deliverability Studies if the affected Transmission Owner(s) and MISO do not see a
reliability issue after a review:
1) Incomplete conditions associated with the A10 process which have the MTEP
classification of “Other” and which have in-service dates delayed for five (5) years or longer
from their initially proposed in-service dates in MTEP
2) Incomplete conditions associated with the A10 process which have been cancelled and
not replaced in the MTEP process, or if replaced but the replacement project is not to fix
an overload issue contributed by the generator according to the A10 study threshold
criteria.

6.6.6.
Annual ERIS Studies and QOL Coordination
The amount of ERIS injection that clears the Annual ERIS evaluation for the next Planning Year
will not be subject to the Quarterly Operating Limits (QOL) studies for all 4 quarters of that year.

Any ERIS injection that does not clear the Annual ERIS evaluation for the next Planning Year will
be included in the QOL studies for all 4 quarters of that year. The customer may choose not to be
included in the QOL studies if they wish to be limited by the Annual ERIS evaluation results for all
4 quarters of that year.

6.7. Modification of Existing Generating Facilities

6.7.1.
Generating Facility Modification Process
Generating Facility Modification shall mean modification to an Existing Generating Facility,
including comparable replacement of only a portion of the equipment at the Existing Generating
Facility. If a planned modification to an Existing Generating Facility (with unsuspended
interconnection rights) is expected by the IC (or generator owner) to have material (adverse)
impact on the Transmission System with respect to: i) steady-state thermal or voltage limits, or ii)
dynamic system stability and response, or iii) short-circuit capability limit; the IC shall submit a
request in writing to MISO for a Generating Facility Modification prior to performing any
permanent21 modification22,23 to an Existing Generating Facility. The request shall be in the form
of a letter describing the planned changes to the Existing Generating Facility and all relevant data
and analysis. The request shall be submitted to MISO at the following address:
Director, Resource Utilization
MISO
720 West City Center Drive
Carmel, IN 46032

Generating Facility maintenance that requires replacement of components with newer
comparable components to ensure continued or enhanced reliable operation of the Generating
Facility will generally be considered to have de minimis impact on the transmission system. It is
the IC’s responsibility to support any determination that the planned modification is not expected


21 Temporary modifications do not require changes to the GIA. Temporary modifications made while waiting on the comparable
part to be delivered and modifications made as a result of equipment failure to support continued reliability may not be
“comparable.” However, such modifications do not require changes to the GIA, as they are a part of an owner’s routine
maintenance and/or equipment failure processes and are not subject to MISO review.
22 Any modification that may result in an increase in net injection above the existing Interconnection Service will require a new
Interconnection Request to be submitted to MISO prior to an increase in actual injection at the POI.
23 Generating Facility modification for complete fuel conversion that does not involve complete tear down of an existing
Generating Facility will be eligible for generator modification process.

to result in degradation of transmission system reliability. The evidence to support this engineering
judgment may be an assessment that is performed by the IC, TO, or a third party.

For on-going generator maintenance, where the replacement components are comparable and
impacts are expected to be de minimis, there is no need for the submission of information to MISO
for determination of material (adverse) impacts. In cases where replacement components are not
comparable, MISO will determine if the change is a Qualitied Change.

A determination of whether a planned change has a de minimis impact on the transmission system
shall be made using good engineering judgment and shall be based on the decision made or
opinion rendered by a qualified engineer. In making this determination, the qualified engineer shall
take into account all available data and rely on his or her experience with the generation
technology and transmission system and knowledge of NERC standards. Additionally, the IC may
request a meeting with MISO and the TO prior to submitting a request for Generating Facility
Modification evaluation to discuss the planned change and any need for additional studies.

If the IC is certain that the planned change to the Existing Generating Facility would constitute a
Qualified Change, the IC can enter the DPP cycle in MISO’s Generator Interconnection queue by
submitting a new IR.

6.7.1.1.
Milestones
A deposit is not required if the IC submits engineering studies supporting a determination that the
planned change is not a Qualified Change. However, a fee may be required at a later date to
reflect the cost of review, or a study deposit may be collected if the analysis submitted by the IC
is incomplete or does not demonstrate that the planned change is not Qualified Change.

6.7.1.2.
Evaluation of Generating Facility Modification
Requests submitted to MISO must evaluate any change in operating characteristics of the
Existing Generating Facility that is different than what was studied in the interconnection process
or reflected in its interconnection agreement. The IC must submit its studies/analyses that are
performed by a qualified subject matter expert to MISO for consideration in its review. Like-for-
Like (or comparable) replacements and refurbishments of existing equipment are not Qualified
Changes, and MISO’s evaluation of these equipment is not required unless the IC anticipates that
such changes may have material impact on the Transmission System, per the criteria defined in
Section 6.7.4 of this BPM.

MISO will respond to the IC within 30 days and provide the path for the IC to amend their GIA, as
necessary, or to submit a new IR.

























Figure 6-3 Flowchart describing Generating Facility Modification evaluation and Qualified Change
determination.

6.7.2.
Generating Facility Replacement Process
Generating Facility Replacement process (pursuant to Section 3.7 of Attachment X to MISO Tariff)
can be used if an IC is planning to replace one or more generating units and/or storage devices
at an Existing Generating Facility with one or more new generating units or storage devices at the
same electrical Point of Interconnection (i.e., same voltage level at the interconnecting substation)
as the Existing Generating Facility.
No
Yes
Process
Request
Amend GIA, as
necessary
 Generating Facility Review
 Is the
modification a
Qualified
Submit a new IR
for MM
evaluation

To initiate the Generating Facility Replacement process, an IC can submit an Interconnection
Request (Appendix 1 to Attachment X) to MISO accompanied by a Non-Refundable Deposit 1
(D1) and a study deposit in the amount of 150,000. The request can be submitted at any time if it
meets all the requirements as described in Section 3.7 of Attachment X to MISO Tariff. ICs must
initiate Replacement IRs through the online application tool. ICs must establish a profile on the
MISO website prior to requesting access to the online application tool via the MISO Generator
Interconnection page. The online application tool, instructions for establishing a profile, and an IC
training
module
may
be
accessed
through
MISO’s
website
at:
https://www.misoenergy.org/planning/resource-utilization/generator-interconnection/. The online
application tool contains all data required by Tariff Attachment X, Appendix 1 and enables ICs to
submit data to MISO in the form of Appendix 1. MISO will only accept Replacement IRs completed
using the online application tool. In the event that MISO experiences an outage or other technical
difficulty that prevents Interconnection Customers from completing and submitting Replacement
IRs, MISO will communicate an alternative method for affected Interconnection Customers to
submit their Replacement IR. Once the complete application is received, MISO will assign a
queue number for the replacement request and will post them publicly on MISO’s Generator
Interconnection queue webpage.

If the existing generating unit has a shared legacy GIA with other generating units that are not
part of the replacement request, the IC shall request MISO to convert existing shared legacy GIA
to current pro forma GIA, representing the shared generators, prior to submitting the replacement
request. As part of a Generator Replacement request, IC may request to split a shared legacy
GIA to multiple GIAs.

6.7.2.1.
Evaluation Process for Generating Facility Replacement
Requests
Generating Facility Replacement evaluation will consist of two studies: (i) Replacement Impact
Study, and (ii) Reliability Assessment Study.

Replacement Impact Study
Replacement Impact study is an engineering study that evaluates the impact of a proposed
Generating Facility Replacement on the reliability of the Transmission System when compared to
the Existing Generating Facility. This study will use the models from the latest DPP cycle for which
the DPP Phase 3 System Impact Study is completed. These models will correspond to the MISO
region applicable to the replacement request and will include the Network Upgrades from the

corresponding DPP study. The dispatch assumptions for the study are detailed in Table 6-1. This
study will utilize Material Modification evaluation criteria as set forth in Section 6.7.4 of this BPM.
If MISO determines that the replacement request is not a Qualified Change, the IC can move
forward with the requested replacement provided that Reliability Assessment Study also shows
no reliability concerns or that mitigations will be in place for the issues identified. The replacement
unit shall meet FERC Order 827, FERC Order 661/661-A, and FERC Order 842 requirements, as
applicable.

Table 6-1: Dispatch Assumptions for Replacement Impact Study

Benchmark Case
Study Case
Retiring Unit
ON
OFF
Replacement Unit
OFF
ON
•
Dispatch of the Retiring Unit and Replacement Unit is by fuel type as set forth in
Section 6.1.1.1.2 of this BPM.
•
For those replacement requests where the Interconnection Service (IS) requested for
the Replacement Unit is less than that of the Retiring Unit, the Retiring Unit and
Replacement Unit is dispatched by fuel type and in accordance with the IS requested
in the replacement request.

Reliability Assessment Study
Reliability Assessment Study is an engineering study that evaluates the impact of a proposed
Generating Facility Replacement on the reliability of Transmission System during the time period
between the date that the Existing Generating Facility ceases commercial operations and the
Commercial Operation Date of the Replacement Generating Facility. The Reliability Assessment
Study assumptions will be similar to Attachment Y (Suspension/Retirement) study as set forth in
Section 6.2 of MISO BPM-020. In no case will the existing unit be eligible as a System Support
Resource (SSR) through the Generating Facility Replacement process. The study year of the
base model will reflect the date of cessation of operation of Existing Generating Facility. The
dispatch assumptions for the study are detailed in Table 6-2. The Existing Generating Facility
shall be responsible for mitigating any reliability violation identified in the Reliability Assessment
Study and may not cease operations until all mitigations are implemented or are in service.
Mitigation for this interim period may, as applicable, include: (i) redispatch/reconfiguration through
operator instruction; and (ii) remedial action scheme or any other operating steps depending upon
the type of reliability violation identified. If there are no reliability concerns or if all identified

reliability concerns will have mitigations in place, the IC can move forward with the requested
replacement provided that Replacement Impact Study also shows no material adverse impact
(not a Qualified Change).

Table 6-2: Dispatch Assumptions for Reliability Assessment Study

Benchmark Case
Study Case
Retiring Unit
ON
OFF
Replacement Unit
OFF
OFF

Reliability Assessment Study will not be performed: (1) if there is no gap period between the date
that the Existing Generating Facility ceases commercial operations and the Commercial
Operation Date of the Replacement Generating Facility, or (2) if the Existing Generating Facility
is in Forced Outage or has an approved Attachment Y suspension per MISO Tariff.

Figure 6-4 Flow Diagram describing Generating Facility Replacement Process
*Request will be evaluated in the order they are received
** If the Replacement Impact Study identifies material adverse impacts and/or the Reliability Assessment Study identifies reliability
concerns that cannot be mitigated, the Generating Facility Replacement process cannot be utilized.  To continue with the
replacement, the IC will need to submit a new Interconnection Request to the Interconnection Queue, follow the 3-phase DPP
process for the replacement unit, and submit an Attachment Y request for retirement of the Existing Generating Facility, as
appropriate. Alternatively, the IC can withdraw the replacement request.

MISO will tender a draft/amend GIA after Final Facility Study Report is
provided to the IC
(30 Calendar Days)
Interconnection Facility Study (if needed)
(90 Calendar Days)
If there are no material adverse impacts or reliability concerns, IC can
decide to proceed or withdraw**
(30 Calendar Days)
Replacement Impact Study & Reliability Assessment Study
(180 Calendar Days)
IC submits Replacement Request to MISO*
(Study Deposit = $150,000)

6.7.3.
Surplus Interconnection Service
Surplus Interconnection Service (pursuant to Attachment X to MISO Tariff) shall mean any
Interconnection Service that is derived from the unneeded portion of Interconnection Service
established in a GIA or in agreement with, or under the tariff of, a Transmission Owner prior to
integration into MISO, such that if Surplus Interconnection Service is utilized the total amount of
Interconnection Service at the Point of Interconnection would remain the same.

To request for Surplus Interconnection Service, an IC can submit an Interconnection Request
(Appendix 1 to Attachment X) to MISO accompanied by a Non-Refundable Deposit 1 (D1) and a
study deposit in the amount of $150,000. The request can be submitted at any time with the
Commercial Operation Date at least one year after the submission date of the Surplus
Interconnection Request if it meets all the requirements described in Attachment X to MISO Tariff.
ICs must initiate Surplus IRs through the online application tool. ICs must establish a profile on
the MISO website prior to requesting access to the online application tool via the MISO Generator
Interconnection page. The online application tool, instructions for establishing a profile, and an IC
training
module
may
be
accessed
through
MISO’s
website
at:
https://www.misoenergy.org/planning/resource-utilization/generator-interconnection/. The online
application tool contains all data required by Tariff Attachment X, Appendix 1 and enables ICs to
submit data to MISO in the form of Appendix 1. MISO will only accept Surplus IRs completed
using the online application tool. In the event that MISO experiences an outage or other technical
difficulty that prevents Interconnection Customers from completing and submitting Surplus IRs,
MISO will communicate an alternative method for affected Interconnection Customers to submit
their Surplus IR. As part of the Interconnection Request, the IC must notify MISO whether the
sole operation of the Surplus Interconnection Service Generating Facility at the Point of
Interconnection should also be included as a part of Interconnection Study for the Surplus
Interconnection Service. Such studies will identify whether the Surplus Interconnection Service
Generating Facility can be solely and reliably operated after the retirement of the Existing
Generating Facility, if applicable. If this scenario shows no material adverse impact in the
Interconnection Study, then this can be used to satisfy one of the requirements for continuation
of Surplus Interconnection Service after retirement or cessation of commercial operation of an
Existing Generating Facility for a limited period not to exceed one (1) year (Section 3.3.1.3 of
Attachment X to MISO Tariff). Once the complete application is received, MISO will assign a
Surplus Interconnection Service request number for the Surplus Interconnection Request and will
post them publicly on MISO’s Generator Interconnection queue webpage.

The Interconnection Study for Surplus Interconnection Service consists of reactive power, short
circuit/fault duty, and stability analyses. If MISO is unable to verify that the Existing Generating
Facility was previously studied for the granted level of Interconnection Service, MISO may perform
steady state analyses to demonstrate reliable operation of the Surplus Interconnection. For
identified applicable studies, MISO will utilize Qualified Change evaluation criteria as set forth in
Section 6.7.4 of this BPM. The study will use the regional DPP Phase 3 models from the latest
DPP cycle for which the Interconnection Customer Decision Point II is completed. These models
will correspond to the MISO region applicable to the Surplus Interconnection Request and will
include the Network Upgrades from the corresponding DPP study. The study will use fuel type
dispatch assumptions as set forth in Section 6.1.1.1.2 of this BPM, as applicable24. If MISO
determines that the Surplus Interconnection Service proposed in the Surplus Interconnection
Request would not result in material adverse impact on the Transmission System and/or Affected
Systems, as compared to the impacts that are created by the Existing Generating Facility without
the inclusion of the proposed Surplus Interconnection Service, the IC can move forward with the
requested Surplus Interconnection Service.



24 Default fuel type dispatch assumptions may change depending on the application and agreement, details to be finalized during the study
scope preparation.

Figure 6-5 Flow Diagram Describing Surplus Interconnection Process

* Request will be evaluated in the order they are received
** If the Interconnection Study for Surplus Interconnection Service identifies material adverse impacts on the Transmission System
and/or Affected System, the IC shall proceed through Definitive Planning Phase cycle similar to a request for interconnection of a
new Generating Facility. Alternatively, the IC can withdraw the Surplus Interconnection Request.

6.7.4.
Qualified Change Evaluation Criteria
For Generator Facility Modification evaluation, MISO may perform steady-state (thermal/voltage),
reactive power, short circuit/fault duty, and stability analyses, as necessary, using the applicable
reliability criteria consistent with DPP study as set forth in Section 6.1.1.1.4 of this BPM to ensure
that required reliability conditions are studied. The type of contingencies used for this evaluation
will be consistent with DPP study as set forth in Section 6.1 of this BPM. Upon receipt of the
Qualified Change evaluation from the IC, MISO will notify the impacted TO(s) and will coordinate
with the impacted TO(s) during the study process.
MISO will tender a draft GIA after Final Facility Study Report is provided
to the IC
(30 Calendar Days)
Interconnection Facility Study (if needed)
(90 Calendar Days)
If there are no material adverse impacts, IC can decide to proceed or
withdraw**
(30 Calendar Days)
Within 30 Calendar Days, MISO will commence Interconnection Study for
Surplus Interconnection Service
(90 Calendar Days)
IC submits Surplus Interconnection Request to MISO*
(Study Deposit = $150,000)

The following criteria will be used to determine whether the change to an Existing Generating
Facility is a Qualified Change:

•
Any change in expected output of the Generating Facility that is higher than what was
studied in the interconnection process unless a control scheme is employed to limit the
injection at the POI to ERIS limit.
•
An increase in short circuit current that degrades transmission system reliability.
•
Angular stability performance and dynamic response that degrades transmission system
reliability.
•
Violation of steady-state thermal or voltage limits caused by the planned change utilizing
the DPP criteria as set forth in Sections 6.1.1.1.8 and 6.1.1.2 of this BPM.
•
Any worsening of a pre-existing adverse condition — including thermal overloads,
voltage deviations, or stability margins — relative to the pre-modification baseline,
regardless of whether such condition predates the proposed modification.
•
Non-compliance with applicable FERC Order requirements, including but not limited to
FERC Orders 827, 661/661-A, and 842, where the modified or replaced component was
identified in prior interconnection studies as a contributing factor to such non-
compliance. The IC shall demonstrate that the replacement component meets all
applicable FERC Order requirements in effect at the time of the modification request.
