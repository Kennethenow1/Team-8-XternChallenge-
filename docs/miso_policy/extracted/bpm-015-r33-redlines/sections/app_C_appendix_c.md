---
doc_id: bpm-015-r33-redlines
section_id: app_C
section_title: Appendix C
start_page: 147
end_page: 152
status: redlines
source_pdf: 02_bpm-015-r33_generator_interconnection_redlines.pdf
---

# app_C Appendix C

Appendix C
MISO Generation Deliverability Study Method
i.
Introduction
This document serves the purpose of providing the methodology to determine whether a
generator can be certified as deliverable under the MISO Tariff as per.
(1) Attachment X (Generator Interconnection Process for NRIS), or
(2) Module E (Resource Adequacy Requirements).

A generator that is certified deliverable through MISO’s deliverability study could be designated
by Load within the MISO’s Market footprint to satisfy its Resource Adequacy requirement as
specified in Module E.

The generator deliverability study analyzes the ability of a group of generators to operate at their
maximum capability without being constrained (“bottled up”) by the electric transmission system.
The test is performed in a 3-step process as outlined below.

Any new generator or existing non-Designated Network Resource (non-DNR) applying for NRIS
under Attachment X of the MISO Tariff can be considered deliverable to the MISO aggregate
load if it passes the deliverability study. The deliverability study was applied to existing
generating resources prior to the start of MISO’s Energy Market; as well, it has been and can be
applied prior to integration of any new Balancing Authority into MISO.

The generation deliverability study is one piece of MISO’s DPP cycle and is also included in the
annual process for MTEP. MISO’s deliverability study in DPP cycle determines the deliverability
of study generators requesting NRIS and ensures that existing resources with NRIS remain
deliverable, including units in suspension. The annual MTEP deliverability study ensures that
the deliverability of all NRIS generators in MISO is maintained as future transmission is planned.

ii.
Study Method
Step 1: Create Deliverability Model
Purpose of Step 1: Establish a power-flow model with MISO summer-peak load and interchange
served by MISO resources with NRIS.

The deliverability model is developed from the ERIS study model used for the DPP cycle and
region under study, with all prior-queued generators at their granted NRIS value and their
associated network upgrades included. If there is any change in the network before the five (5)
year horizon that may impact deliverability of the generators under study, those issues can be
addressed during scoping and model review. As in ERIS models, Affected System units with
queue priority are included. ERIS only generation is turned off and un-dispatched NRIS
generation is turned on to at least pgen = 0, such that total generation in MISO classic and
MISO South in the deliverability model is equal to total generation in MISO classic and MISO
South in the Study model. For the Annual MTEP Deliverability Study, only NRIS generators with
signed GIAs or PGIAs will be dispatched up to their granted levels. As such, all NRIS
generators are turned on, and any ERIS generators are “turned off” and remain off in the model
for analysis with the exception of Behind the Meter Generators (BTMG) which are left as-is. For
the purpose of maintaining a conservative approach to a deliverability study, Behind the Meter
Generator (BTMG) units are treated as NRIS generators and are left on in the model at their
existing dispatch levels, even though they technically do not have MISO NRIS. ERIS generators
with Firm Transmission Service are to be treated the same as NRIS generators.

For the DPP deliverability study, study generators for the cycle are ramped up to their requested
NR levels by TARA Deliverability tool. The study generators requesting NRIS are adjusted
automatically by TARA Deliverability tool which provides a more conservative approach to
flowgate identification.

In the study model for the annual MTEP deliverability study, all NRIS generators are counted as
study generators, and are dispatched according to LBA methodology to offset the ERIS
generators being turned off.

The Deliverability case will include approved MTEP projects and those targeted for approval in
the applicable MTEP cycle.

If a deliverability model is desired by stakeholders, MISO will provide it on a case-by-case basis.

Step 2: Use PowerGEM TARA to capture potential deliverability constraints.

Purpose of Step 2: Use TARA to find branch violations on monitored elements throughout the
MISO system caused by study generators. This step returns a list of all violations, which can be
refined using post-processing to find the worst-case violations for each monitored element.

TARA Input Files:

Power-flow file (.raw): The Deliverability case file created in Step 1.

Subsystem file (.sub): Includes the subsystems MISO_EX, MISO_IM, and any other
subsystems required to support related Monitored Facility (.mon) files and Contingency (.con)
files.

MISO_EX and MISO_IM both contain all areas located in the MISO market footprint. By
including all of MISO as both the source and sink for the system, every generator’s deliverability
will be studied by TARA Deliverability tool against every other part of the MISO system when
identifying study flowgates. (For the purposes of this Deliverability analysis, a "flowgate" is
defined as a constrained mon-con pair. These flowgates do not necessarily follow any of the
legacy flowgates in the MISO area used over the years.) The original interchange for areas in
MISO and its neighbors is maintained during this redispatch by proportionally scaling generation
in the MISO_EX area.

For DPP studies, study generators part of the DPP cycle under study are defined as part of the
MISO_EX subsystem and treated separately from other NRIS generators within MISO by
including them in the special STUDY block in the subsystem file. In the MTEP Deliverability
Analysis, all NRIS generators in MISO_EX footprint are treated as study generators.

Monitor file (.mon): Include all transmission facilities under MISO’s functional control as well as
appropriate external transmission facilities of neighboring entities.

Contingency file (.con): For DPP studies, use the ERIS study contingency files corresponding to
the study model that is previously reviewed by the Expansion Planning Group and TOs in the
DPP ad-hoc study group. Contingency files for deliverability studies should only contain P1 and

P0 contingencies. Additionally, TARA automatically generates and tests N-1 contingencies (auto
singles) of monitored elements in the MISO_EX and seams regions subsystem.

For the annual MTEP deliverability study, use the same contingency files corresponding to the 5
years out summer peak MTEP model as those used for annual MTEP reliability assessment.

TARA analysis:

Flowgate Screening: TARA Deliverability tool is able to automatically screen for flowgates by
creating monitored element-contingency pairs with a DF greater than a prescribed value. Up to
8000 MW is transferred from MISO_EX to MISO_IM while keeping the MISO interchange at the
same level. Through a trial-and-error method, MISO determined that an 8000 MW transfer cap
is sufficient to reveal all credible overloads (this transfer parameter will be reviewed and revised
if needed for any specific study). For the purposes of the deliverability study, all flowgates are
identified for which at least one study generator has a DFAX greater than or equal to 5%, and
the flowgate itself has a DC loading of greater than or equal to 70%.

Stressed Dispatch: For each flowgate created by TARA Deliverability tool, the top 30 generators
contributing to the flowgate (i.e., the generators with the highest DFAX on the flowgate) have
their output increased to their granted NRIS for existing/higher-queued generators or the
requested NRIS for study generators. To compensate for the increase in system generation,
generators in the rest of MISO_IM are uniformly scaled down.


The purpose of this dispatch is to create a severe, yet credible, dispatch for each identified
flowgate in the deliverability model.

If the DC-solution-method loading on the line is greater than 70%, the list of harmers is saved
for AC verification.

Loading Adder: The impact of flows from large offline generators outside of the top 30 DF list
are not captured in previous steps but can be non-negligible. To account for the impact of large
NRIS generators that are outside of the Top 30 DFAX list, any NRIS generator whose DFAX is
greater than 5% and whose MW impact (Pmax * DFAX) is greater than 20% of the line rating is
turned on to its NRIS level as part of the stressed dispatch.

AC Verification: An AC power flow analysis is automatically performed by TARA Deliverability
tool for all flowgates with a DC loading of greater than 70%. AC analysis confirms loading
violations identified during DC analysis in order to appropriately account for the impact of
reactive power loading, which can yield higher total line loadings.

For each flowgate, TARA calculates the shared generation deduction required for the study
generators contributing to the flowgate’s AC-solution-method violation. The shared deduction is
the amount by which each study generator affecting a given flowgate must be scaled down in
order to prevent loading violations on the flowgate. The deduction is proportionally taken from
each study generator affecting a particular flowgate. If a particular monitored element becomes
a flowgate under multiple contingency conditions, the contingency requiring the highest
deduction is used.

Step 3: Results

If a study generator does not contribute more than 5% of the DFAX on any flowgate with a
loading violation, it is considered fully deliverable, subject to any conditions to the GIA
(Appendix A10). If a study generator does contribute to a flowgate with a loading violation, it is
not considered fully deliverable without a network upgrade. The shared deduction is calculated
by uniformly scaling down the study generators in the top 30 harmers until the flowgate is no
longer overloaded.

For each study generator that is not fully deliverable, the flowgates for which it is in the top 30
list are ranked in order of the shared deductions. A study generator is considered deliverable up
to a MW value where no overloads occur on any flowgate, as determined by the shared

deduction, assuming all associated generator requests limit their NR request to the shared
deduction value specified in the deliverability results.

All deliverability limiting constraints should be verified as a part of the Ad Hoc study group
process.

Existing Operating guides are considered in deliverability study only if the guide does not
involve the redispatch of existing NRIS generators, and it is an acceptable practice as per the
applicable planning criteria.

For an IR under study, the IC can choose either to make the network upgrades to eliminate the
constraint, or to proceed with ERIS instead of NRIS for the portion of their NRIS request that is
not deliverable.
