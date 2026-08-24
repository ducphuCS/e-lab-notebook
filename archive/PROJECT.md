# Electronic Lab Notebooks

## Context

Electronic Lab Notebook is the brain of every Research and Development (R&D) department. It is a digital system used to plan, record, store, and manage experimental data, protocols, and results. It is used by formulators and researchers to plan, execute, and document their experiments. It is also used to collaborate with other researchers and to share their findings.

The first version is not living up to its expectations. There are few users who adapts the system to their daily routine. One of the reasons is that the system is not well-designed for the current workflow. Users claimed that too many changes have to be done for them to use the system. Therefore, the system doesn't offer any significant help to users's current need, beside being a compulsory tool.

This project is a redesign of the system to better fit the needs of the users. The main goal is to make the system more user-friendly and to make it a tool that formulators and researchers will actually want to use.

## Preliminary research

First of all, it needs to align or slightly modify how users are working. So the question is who are the intended users and what are they doing? Our main consumers are the formulators whose task is to create winning formulations, researchers whose tasks are vary from shelf-life, microbiology, packageing, processing, etc. Therefore, each group will have their own evaluation criterias, as below:

1. Formulators. Their daily works include figuring out which formulation to create next based on some information such as consumer testing, sensory evaluation. The experiments that we want to record is tied to formulation where changes are made. Therefore, the system needs to be flexible enough to allow users to quickly modify, duplicate the formulations and provide automation for tasks likes pricing estimation, constraints evaluation, etc.

2. Researchers. They mostly work with samples with or without knowledge about the formulations behind. Therefore, the system needs to be tied with samples to integrate with how researchers are currently working. The selling value would be what information about the sample that the system can present to researchers.

Secondly, there are reviewers whose task is to read, provide scientific sources likes papers and/or patents, and ask quesiton to help the Design of Experiments (DoEs) more structured and reasonable. The system need to allow the reviewers easy access to the DoEs, add attachments, and facilitate the collaboration between reviewers and users.

The third point is about management. Since the system is intended to deeply integrate with daily routine, it also need a mechanic to manage workload, assign person-in-charge, etc. Both team leaders and team members will be users of the system. Therefore, the system need to support different roles with different permissions.

Fourthly, every system need a protocol to exchange data with others. The system also require ways to connect with other system. One crucial wish is the system can connect to QL One for lab test results, which is an important part of team Shelf-life and Stability.

## Definitions

There are concepts or words that will be used throught out this documentation and, especially, when implementing the application. We dedicate this sections to define them clearly to ensure everyone is on the same page.

**Formulations**
: A table consists of the ingredients, unit of measures and the quantity of ingredients. Ingredients can be described as a combination of an item code and an item description. Ingredients can be one single ingredient, or a combination of two or more sub-ingredients. Each formulation is presented by one or more than one samples.

**Experiment**
: An experiment describes what formulators are intended to do in their next formulations, including objectives, hypothesis, factors, levels of factors, outcomes and results. It contains a set of formulations which are the results of the designated factors.

## Action standards

This section presents the expected quality of the deliverables. To measure if the deliverables are acceptable, we declare our success criterias as follows:

- The application must allow different types of users, namely formulators, formulator managers, researchers, system adminstrators.
- Formulators must have the *Plan* mode where they can design an experiment before conducting it. *Plan* mode allow formulators to quickly draft their experiments and record their intention.

Note that the responsibility and expectations for the application can change, and therefore, these criterias can be different in the future. However, every modification to this section is important and must be recorded and treat with care.

## Problem statements

In this section, we discuss about the pathway to achieve our desired outcome above.

