import { Document, Packer, Paragraph, Table, TableCell, TableRow, WidthType, AlignmentType, HeadingLevel } from 'docx';
import { saveAs } from 'file-saver';
import { AnalysisItem } from '@/components/Dashboard';
import { PatientInfo } from '@/components/Dashboard';

interface ReportTotals {
  claimed: number;
  approved: number;
  rejected: number;
  reimbursed?: number;
}

export const generateReport = async (
  analysisResults: AnalysisItem[],
  totals: ReportTotals,
  patientInfo?: PatientInfo
): Promise<void> => {
  try {
    const doc = new Document({
      sections: [
        {
          properties: {},
          children: [
            // Header
            new Paragraph({
              text: "Medical Bill Analysis Report",
              heading: HeadingLevel.TITLE,
              alignment: AlignmentType.CENTER,
              spacing: { after: 400 }
            }),
            
            new Paragraph({
              text: `Generated on: ${new Date().toLocaleDateString('en-IN', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              })}`,
              alignment: AlignmentType.CENTER,
              spacing: { after: 600 }
            }),

            // Patient Information Section
            ...(patientInfo ? [
              new Paragraph({
                text: "Patient Information",
                heading: HeadingLevel.HEADING_1,
                spacing: { before: 400, after: 200 }
              }),
              new Paragraph({
                text: `Patient Name: ${patientInfo.name}`,
                spacing: { after: 100 }
              }),
              new Paragraph({
                text: `Relation: ${patientInfo.relation}`,
                spacing: { after: 100 }
              }),
              ...(patientInfo.age ? [new Paragraph({
                text: `Age: ${patientInfo.age} years`,
                spacing: { after: 100 }
              })] : []),
              ...(patientInfo.gender ? [new Paragraph({
                text: `Gender: ${patientInfo.gender}`,
                spacing: { after: 300 }
              })] : []),
              new Paragraph({
                text: "",
                spacing: { after: 200 }
              })
            ] : []),

            // Executive Summary
            new Paragraph({
              text: "Executive Summary",
              heading: HeadingLevel.HEADING_1,
              spacing: { before: 400, after: 200 }
            }),

            new Paragraph({
              text: `Total Items Analyzed: ${analysisResults.length}`,
              spacing: { after: 100 }
            }),

            new Paragraph({
              text: `Admissible Items: ${analysisResults.filter(item => item.status === 'Admissible').length}`,
              spacing: { after: 100 }
            }),

            new Paragraph({
              text: `Not Admissible Items: ${analysisResults.filter(item => item.status === 'Not Admissible').length}`,
              spacing: { after: 300 }
            }),

            // Financial Summary Table
            new Paragraph({
              text: "Financial Summary",
              heading: HeadingLevel.HEADING_2,
              spacing: { before: 400, after: 200 }
            }),

            new Table({
              width: {
                size: 100,
                type: WidthType.PERCENTAGE,
              },
              rows: [
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph({ text: "Category", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Amount (₹)", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph("Total Claimed")],
                    }),
                    new TableCell({
                      children: [new Paragraph({ 
                        text: totals.claimed.toLocaleString('en-IN'),
                        alignment: AlignmentType.RIGHT 
                      })],
                    }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph("Total Approved")],
                    }),
                    new TableCell({
                      children: [new Paragraph({ 
                        text: totals.approved.toLocaleString('en-IN'),
                        alignment: AlignmentType.RIGHT 
                      })],
                    }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph("Total Reimbursed")],
                    }),
                    new TableCell({
                      children: [new Paragraph({ 
                        text: (totals.reimbursed || 0).toLocaleString('en-IN'),
                        alignment: AlignmentType.RIGHT 
                      })],
                    }),
                  ],
                }),
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph({ text: "Approval Rate", })],
                      shading: { fill: "F0F0F0" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ 
                        text: `${((totals.approved / totals.claimed) * 100).toFixed(1)}%`,
                        alignment: AlignmentType.RIGHT 
                      })],
                      shading: { fill: "F0F0F0" }
                    }),
                  ],
                }),
              ],
            }),

            // Detailed Analysis
            new Paragraph({
              text: "Detailed Item Analysis",
              heading: HeadingLevel.HEADING_2,
              spacing: { before: 600, after: 200 }
            }),

            new Table({
              width: {
                size: 100,
                type: WidthType.PERCENTAGE,
              },
              rows: [
                new TableRow({
                  children: [
                    new TableCell({
                      children: [new Paragraph({ text: "Item Name", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Category", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Claimed (₹)", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Status", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Approved (₹)", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                    new TableCell({
                      children: [new Paragraph({ text: "Reimbursed (₹)", alignment: AlignmentType.CENTER })],
                      shading: { fill: "CCCCCC" }
                    }),
                  ],
                }),
                ...analysisResults.map(item => 
                  new TableRow({
                    children: [
                      new TableCell({
                        children: [new Paragraph(item.itemName)],
                      }),
                      new TableCell({
                        children: [new Paragraph(item.category || 'General')],
                      }),
                      new TableCell({
                        children: [new Paragraph({ 
                          text: item.claimedPrice.toLocaleString('en-IN'),
                          alignment: AlignmentType.RIGHT 
                        })],
                      }),
                      new TableCell({
                        children: [new Paragraph({ 
                          text: item.status,
                          alignment: AlignmentType.CENTER 
                        })],
                        shading: { 
                          fill: item.status === 'Admissible' ? "E8F5E8" : "FEE8E8" 
                        }
                      }),
                      new TableCell({
                        children: [new Paragraph({ 
                          text: item.approvedPrice.toLocaleString('en-IN'),
                          alignment: AlignmentType.RIGHT 
                        })],
                      }),
                      new TableCell({
                        children: [new Paragraph({ 
                          text: (item.reimbursementAmount || 0).toLocaleString('en-IN'),
                          alignment: AlignmentType.RIGHT 
                        })],
                      }),
                    ],
                  })
                ),
              ],
            }),

            // Category Breakdown
            new Paragraph({
              text: "Category Breakdown",
              heading: HeadingLevel.HEADING_2,
              spacing: { before: 600, after: 200 }
            }),

            ...generateCategoryBreakdown(analysisResults),

            // Footer
            new Paragraph({
              text: "This report was generated automatically by Medical Bill Analyzer.",
              alignment: AlignmentType.CENTER,
              spacing: { before: 600 }
            }),
          ],
        },
      ],
    });

    const buffer = await Packer.toBlob(doc);
    const fileName = `Medical_Bill_Analysis_${new Date().toISOString().split('T')[0]}.docx`;
    saveAs(buffer, fileName);
  } catch (error) {
    console.error('Error generating report:', error);
    throw error;
  }
};

const generateCategoryBreakdown = (analysisResults: AnalysisItem[]): Paragraph[] => {
  const categories = [...new Set(analysisResults.map(item => item.category || 'General'))];
  const breakdown: Paragraph[] = [];

  categories.forEach(category => {
    const categoryItems = analysisResults.filter(item => (item.category || 'General') === category);
    const categoryTotal = categoryItems.reduce((sum, item) => sum + item.claimedPrice, 0);
    const categoryApproved = categoryItems.reduce((sum, item) => sum + item.approvedPrice, 0);
    const approvalRate = categoryTotal > 0 ? (categoryApproved / categoryTotal) * 100 : 0;

    breakdown.push(
      new Paragraph({
        text: `${category}: ${categoryItems.length} items, ₹${categoryTotal.toLocaleString('en-IN')} claimed, ₹${categoryApproved.toLocaleString('en-IN')} approved (${approvalRate.toFixed(1)}%)`,
        spacing: { after: 100 }
      })
    );
  });

  return breakdown;
};