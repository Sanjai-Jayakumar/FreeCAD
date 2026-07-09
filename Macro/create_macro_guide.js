const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
        LevelFormat, PageBreak } = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Arial", size: 24 }
      }
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 }
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 }
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 }
      }
    ]
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }
        ]
      },
      {
        reference: "numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }
        ]
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      // TITLE PAGE
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 2880, after: 480 },
        children: [
          new TextRun({
            text: "ANVIL CAD Macro System",
            bold: true,
            size: 40,
            font: "Arial"
          })
        ]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 240 },
        children: [
          new TextRun({
            text: "Version-Controlled Workflow Guide",
            size: 28,
            font: "Arial"
          })
        ]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 2880 },
        children: [
          new TextRun({
            text: "February 2026",
            size: 24,
            italics: true,
            font: "Arial"
          })
        ]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // SECTION 1 - Overview
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("1. Overview")]
      }),
      new Paragraph({
        spacing: { after: 240 },
        children: [
          new TextRun("The ANVIL CAD Macro System provides a professional version control workflow for CAD design files. This integrated 5-macro system automatically manages file versioning, preventing data loss and maintaining a complete history of design changes. Unlike manual file naming or scattered backups, this system ensures every modification is tracked with intelligent change detection, preserving assembly links and maintaining clean file organization.")
        ]
      }),
      new Paragraph({
        spacing: { after: 240 },
        children: [
          new TextRun("All five macros work together seamlessly with keyboard shortcuts that mirror familiar shortcuts from other applications, making adoption effortless for new users while providing powerful version control capabilities for experienced engineers.")
        ]
      }),

      // SECTION 2 - The Five Macros
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("2. The Five Macros")]
      }),
      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun("The system consists of five integrated macros:")]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3000, 1800, 4560],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Macro", bold: true, color: "FFFFFF" })] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Keyboard Shortcut", bold: true, color: "FFFFFF" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Purpose", bold: true, color: "FFFFFF" })] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Set Working Directory")] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+Shift+W", font: "Courier New" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Set project folder for all file operations")] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("New File")] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+N", font: "Courier New" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Create new file with type selection")] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Version Save")] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+S", font: "Courier New" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Smart save with automatic versioning")] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Save As")] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+Shift+S", font: "Courier New" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Save As with versioning support")] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({
                width: { size: 3000, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Open File")] })]
              }),
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+O", font: "Courier New" })] })]
              }),
              new TableCell({
                width: { size: 4560, type: WidthType.DXA },
                borders,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Open with intelligent version filtering")] })]
              })
            ]
          })
        ]
      }),

      new Paragraph({ spacing: { before: 240, after: 240 }, children: [new TextRun("")] }),

      new Paragraph({ children: [new PageBreak()] }),

      // SECTION 3 - Quick Start
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("3. Quick Start Guide")]
      }),
      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun("Follow these steps for a typical workflow:")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "Press ", font: "Arial" }), new TextRun({ text: "Ctrl+Shift+W", font: "Courier New", bold: true }), new TextRun({ text: " to set working directory for your project", font: "Arial" })]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "Press ", font: "Arial" }), new TextRun({ text: "Ctrl+N", font: "Courier New", bold: true }), new TextRun({ text: " to create new file (choose Sketch, Part Design, Assembly, or Drawing)", font: "Arial" })]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Design your part in ANVIL CAD using the appropriate workbench")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "Press ", font: "Arial" }), new TextRun({ text: "Ctrl+S", font: "Courier New", bold: true }), new TextRun({ text: " to save (creates MyPart.001.FCStd automatically)", font: "Arial" })]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Make changes to your design as needed")]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text: "Press ", font: "Arial" }), new TextRun({ text: "Ctrl+S", font: "Courier New", bold: true }), new TextRun({ text: " again (creates MyPart.002.FCStd if document was modified)", font: "Arial" })]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun({ text: "Press ", font: "Arial" }), new TextRun({ text: "Ctrl+O", font: "Courier New", bold: true }), new TextRun({ text: " to open files (shows only latest versions by default)", font: "Arial" })]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // SECTION 4 - Detailed Descriptions
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("4. Detailed Macro Descriptions")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("4.1 Set Working Directory")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Opens an intuitive folder browser dialog")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Sets the project working directory for all subsequent file operations")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("All files created and saved will default to this location")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Shows current working directory in window title as \"WD: path\"")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("4.2 New File")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Presents a dialog with 4 file type options arranged in a 2×2 grid")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Options: Sketch, Part Design, Assembly, and Drawing (TechDraw)")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Prompts for Part Name and optional Part Description")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Automatically switches to the appropriate workbench for the selected file type")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("4.3 Version Save (Smart Save)")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Automatically creates versioned files: file.001.FCStd, file.002.FCStd, file.003.FCStd, etc.")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Only creates a new version if the document was actually modified")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Uses intelligent change detection by tracking UndoCount")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Skips save if no changes detected, preventing unnecessary version increment and preserving assembly links")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Displays version number and status in the FreeCAD console")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("4.4 Save As")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Presents standard Save As dialog with integrated version control")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Allows changing both filename and save location")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Automatically updates working directory if a different location is selected")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Maintains version numbering system for the new filename")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("4.5 Open File")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Custom dialog with intelligent version filtering capabilities")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Includes a \"Show all versions\" checkbox for version visibility control")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Unchecked (default): Displays only the latest version of each file, reducing clutter")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Checked: Shows all version files for complete history access")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Prevents accidentally opening outdated versions")]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      // Continue with remaining sections...
      // (Due to length, I'll create the rest in a concise format)

      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("5. Version Control System")]
      }),
      new Paragraph({
        spacing: { after: 120 },
        children: [new TextRun("The versioning system operates automatically:")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Files are automatically numbered sequentially: MyPart.001.FCStd, MyPart.002.FCStd, MyPart.003.FCStd")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Version number increments ONLY when the document has been modified")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Unchanged documents do not create redundant new versions")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Assembly component links remain intact across versions")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Easy reversion to any previous version by simply opening it")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Maintains clean and organized file structure in working directory")]
      }),

      new Paragraph({ children: [new PageBreak()] }),

      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("6. Best Practices")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Always set working directory at the start of each project session")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Use descriptive part names; avoid generic names like \"Unnamed\"")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Save regularly using Ctrl+S for automatic version control")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Keep \"Show all versions\" unchecked when opening files to avoid confusion")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Maintain one working directory per project for better organization")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Rely on version numbers as an automatic backup history system")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("7. Keyboard Shortcuts Reference")]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1800, 2500, 5060],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              new TableCell({
                width: { size: 1800, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Shortcut", bold: true, color: "FFFFFF" })] })]
              }),
              new TableCell({
                width: { size: 2500, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Command", bold: true, color: "FFFFFF" })] })]
              }),
              new TableCell({
                width: { size: 5060, type: WidthType.DXA },
                shading: { fill: "4472C4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Description", bold: true, color: "FFFFFF" })] })]
              })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ width: { size: 1800, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+Shift+W", font: "Courier New" })] })] }),
              new TableCell({ width: { size: 2500, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Set WD")] })] }),
              new TableCell({ width: { size: 5060, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Choose project folder")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ width: { size: 1800, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+N", font: "Courier New" })] })] }),
              new TableCell({ width: { size: 2500, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("New File")] })] }),
              new TableCell({ width: { size: 5060, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Create new with type selection")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ width: { size: 1800, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+S", font: "Courier New" })] })] }),
              new TableCell({ width: { size: 2500, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Version Save")] })] }),
              new TableCell({ width: { size: 5060, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Smart save with auto-versioning")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ width: { size: 1800, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+Shift+S", font: "Courier New" })] })] }),
              new TableCell({ width: { size: 2500, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Save As")] })] }),
              new TableCell({ width: { size: 5060, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Save with new name/location")] })] })
            ]
          }),
          new TableRow({
            children: [
              new TableCell({ width: { size: 1800, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun({ text: "Ctrl+O", font: "Courier New" })] })] }),
              new TableCell({ width: { size: 2500, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Open File")] })] }),
              new TableCell({ width: { size: 5060, type: WidthType.DXA }, borders, margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [new Paragraph({ children: [new TextRun("Open with version filtering")] })] })
            ]
          })
        ]
      }),

      new Paragraph({ spacing: { before: 240 }, children: [new TextRun("")] }),

      new Paragraph({ children: [new PageBreak()] }),

      // SECTION 8 - Troubleshooting
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("8. Troubleshooting")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun("Problem: Working Directory not set error")]
      }),
      new Paragraph({
        spacing: { after: 180 },
        children: [new TextRun({ text: "Solution: ", bold: true }), new TextRun("Press Ctrl+Shift+W to set working directory before creating or saving files.")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun("Problem: Macro not found")]
      }),
      new Paragraph({
        spacing: { after: 180 },
        children: [new TextRun({ text: "Solution: ", bold: true }), new TextRun("Ensure macros are present in the FreeCAD Macro folder. Check the Macro menu for available macros.")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun("Problem: Keyboard shortcuts not working")]
      }),
      new Paragraph({
        spacing: { after: 180 },
        children: [new TextRun({ text: "Solution: ", bold: true }), new TextRun("Restart ANVIL CAD. Keyboard shortcuts are automatically configured on application startup.")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun("Problem: All versions showing when opening files")]
      }),
      new Paragraph({
        spacing: { after: 180 },
        children: [new TextRun({ text: "Solution: ", bold: true }), new TextRun("Uncheck the \"Show all versions\" checkbox in the Open File dialog to display only latest versions.")]
      }),

      new Paragraph({
        heading: HeadingLevel.HEADING_3,
        children: [new TextRun("Problem: Version numbers skipping (e.g., .001 then .003)")]
      }),
      new Paragraph({
        spacing: { after: 240 },
        children: [new TextRun({ text: "Solution: ", bold: true }), new TextRun("This behavior is normal and intentional. Version numbers only increment when the document has been actually modified. Unchanged saves do not create new versions.")]
      }),

      // SECTION 9 - Advanced Tips
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [new TextRun("9. Advanced Tips")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Utilize the Part Description field to add notes, revision comments, or design rationale")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("The version history serves as an automatic backup system for your design work")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Manually delete old versions if disk space becomes a concern, though versions are compressed efficiently")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Working directory can be changed at any time using Ctrl+Shift+W without affecting existing versions")]
      }),
      new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { after: 240 },
        children: [new TextRun("Assembly files maintain correct component links when saving new versions, preventing broken references")]
      }),

      new Paragraph({
        spacing: { before: 480, after: 120 },
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "For additional support, contact the ANVIL CAD team.", italics: true })
        ]
      }),

      new Paragraph({
        spacing: { before: 120 },
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: "Document Version 1.0 - February 2026", size: 20, color: "666666" })
        ]
      })
    ]
  }]
});

// Generate the document
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("BNC_CAD_Macro_System_User_Guide.docx", buffer);
  console.log("✅ User Guide created successfully!");
});
