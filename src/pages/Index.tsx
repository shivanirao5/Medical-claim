import React, { useState } from 'react';
import { FileUploader } from '@/components/FileUploader';
import { Dashboard, AnalysisItem, PatientInfo } from '@/components/Dashboard';
import { ClaimResults } from '@/components/ClaimResults';
import { DocumentParser } from '@/lib/parser';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Stethoscope, FileSearch, TrendingUp, Shield } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

// Index page wires together the upload UI and the two rendering modes:
// 1) Structured view (uses ClaimResults component) when backend returns
//    `claim_items` (preferred path), and
// 2) Legacy dashboard analysis when structured parsing isn't available.
//
// The file also contains error handling to convert technical backend
// errors into friendly toasts for the user.

interface ClaimItem {
  bill_no: string;
  my_date: string;
  amount_spent_on_medicine: number;
  amount_spent_on_test: number;
  amount_spent_on_consultation: number;
  medicine_names: string[];
  test_names: string[];
  doctor_name: string;
  hospital_name: string;
  reimbursement_amount: number;
  editable: boolean;
}

const Index = () => {
  const [analysisResults, setAnalysisResults] = useState<AnalysisItem[]>([]);
  const [claimItems, setClaimItems] = useState<ClaimItem[]>([]);
  const [patientInfo, setPatientInfo] = useState<PatientInfo>({
    name: 'Patient Name Not Found',
    relation: 'Self'
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showStructuredView, setShowStructuredView] = useState(false);
  const [totalPages, setTotalPages] = useState(0);
  const [processingStatus, setProcessingStatus] = useState('completed');
  const [debugMode, setDebugMode] = useState(false);
  const { toast } = useToast();

  // Upload handler: sends files to backend /api/extract and then decides
  // whether to use structured claim view or fallback to the legacy parser.
  // Enhanced with handwritten prescription support
  const handleFilesUploaded = async (files: File[], isHandwritten: boolean = false) => {
    setIsProcessing(true);

    try {
      console.log('Starting analysis with files:', files.map(f => f.name));
      console.log('Handwritten mode:', isHandwritten);

      // Choose the appropriate endpoint
      const endpoint = isHandwritten ? '/api/extract-handwritten' : '/api/extract';
      
      // For handwritten mode, process files individually for better results
      if (isHandwritten && files.length === 1) {
        const formData = new FormData();
        formData.append('file', files[0]);

        const response = await fetch(endpoint, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log('Handwritten processing response:', data);

        // Display enhanced OCR metadata
        if (data.ocr_metadata) {
          toast({
            title: "Handwritten Prescription Processed",
            description: `OCR Confidence: ${data.ocr_metadata.confidence?.toFixed(1)}% | Method: ${data.ocr_metadata.ocr_method || 'Enhanced'}`,
          });
        }

        // Process the results similar to standard processing
        if (data.claim_items && data.claim_items.length > 0) {
          setClaimItems(data.claim_items);
          setTotalPages(data.total_pages || 1);
          setProcessingStatus(data.processing_status || 'completed_handwritten');
          setShowStructuredView(true);
          setShowDashboard(false);
        } else if (data.raw_text) {
          // Even if no structured data, show what was extracted
          toast({
            title: "Text Extracted",
            description: `Extracted ${data.raw_text.length} characters from handwritten prescription`,
          });
        }
      } else {
        // Standard processing for multiple files or non-handwritten
        const formData = new FormData();
        
        if (isHandwritten) {
          // For multiple handwritten files, add the enhancement flag
          formData.append('enhance_handwriting', 'true');
        }
        
        files.forEach(file => formData.append('file', file));

        const response = await fetch('/api/extract', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log('Backend response:', data);

        // If backend returned structured claim items, show the structured UI
        if (data.claim_items && data.claim_items.length > 0) {
          setClaimItems(data.claim_items);
          setTotalPages(data.total_pages || files.length);
          setProcessingStatus(data.processing_status || 'completed');
          setShowStructuredView(true);
          setShowDashboard(false);

          toast({
            title: "Extraction Complete",
            description: `Successfully processed ${data.total_pages || files.length} pages and extracted ${data.claim_items.length} claim items.`,
          });
        } else {
          // If structured data is not available, fallback to the DocumentParser
          // which uses the older analysis pipeline. This ensures backwards
          // compatibility with previously supported flows.
          const parser = DocumentParser.getInstance();
          const { analysisResults: results, patientInfo: extractedPatientInfo } = await parser.processDocuments(files);

          if (results && results.length > 0) {
            setAnalysisResults(results);
            setPatientInfo(extractedPatientInfo);
            setShowDashboard(true);
            setShowStructuredView(false);

            toast({
              title: "Analysis Complete",
              description: `Successfully analyzed ${results.length} items from your medical documents.`,
            });
          } else {
            throw new Error('No analysis results were generated. Please check that your documents contain readable medical information.');
          }
        }
      }
    } catch (error) {
      console.error('Analysis failed:', error);

      // Convert common error messages into friendly toasts so users know
      // what to try next (e.g., upload clearer scans, check network)
      let errorMessage = "Analysis Failed";
      let errorDescription = "Unable to process the uploaded documents.";

      if (error instanceof Error) {
        if (error.message.includes('readable text')) {
          errorMessage = "No Text Found";
          errorDescription = isHandwritten 
            ? "Could not extract readable text from the handwritten prescription. Please ensure the image is clear and well-lit."
            : "Could not extract readable text from the uploaded files. Please ensure your documents contain clear, readable text.";
        } else if (error.message.includes('bill items')) {
          errorMessage = "No Medical Items Found";
          errorDescription = "Could not find any medical items or pricing information in the documents. Please upload documents with clear medical billing details.";
        } else if (error.message.includes('network') || error.message.includes('fetch')) {
          errorMessage = "Network Error";
          errorDescription = "Please check your internet connection and try again.";
        } else {
          errorDescription = error.message;
        }
      }

      toast({
        title: errorMessage,
        description: errorDescription,
        variant: "destructive"
      });
    } finally {
      setIsProcessing(false);
    }
  };

  // Update local claim item state when user edits rows in ClaimResults
  const handleUpdateClaim = (index: number, updatedClaim: ClaimItem) => {
    setClaimItems(prev => 
      prev.map((item, i) => i === index ? updatedClaim : item)
    );
    
    toast({
      title: "Claim Updated",
      description: `Successfully updated claim ${updatedClaim.bill_no}`,
    });
  };

  // Functions for the legacy dashboard to update prices/reimbursements
  const handleUpdateApprovedPrice = (id: string, price: number) => {
    setAnalysisResults(prev => 
      prev.map(item => 
        item.id === id ? { ...item, approvedPrice: price } : item
      )
    );
  };

  const handleUpdateReimbursementAmount = (id: string, amount: number) => {
    setAnalysisResults(prev => 
      prev.map(item => 
        item.id === id ? { ...item, reimbursementAmount: amount } : item
      )
    );
  };

  // A test helper to load sample data locally without calling the backend
  const handleTestWithSampleData = async () => {
    setIsProcessing(true);

    try {
      console.log('Testing with sample data...');

      const sampleResults: AnalysisItem[] = [
        {
          id: 'sample-1',
          itemName: 'Paracetamol 500mg Tablet',
          claimedPrice: 25,
          status: 'Admissible',
          approvedPrice: 25,
          reimbursementAmount: 20,
          category: 'Medicine'
        },
        {
          id: 'sample-2',
          itemName: 'Complete Blood Count (CBC)',
          claimedPrice: 300,
          status: 'Admissible',
          approvedPrice: 300,
          reimbursementAmount: 250,
          category: 'Test'
        },
        {
          id: 'sample-3',
          itemName: 'Doctor Consultation',
          claimedPrice: 200,
          status: 'Admissible',
          approvedPrice: 200,
          reimbursementAmount: 150,
          category: 'Procedure'
        },
        {
          id: 'sample-4',
          itemName: 'X-Ray Chest PA View',
          claimedPrice: 400,
          status: 'Not Admissible',
          approvedPrice: 0,
          reimbursementAmount: 0,
          category: 'Test'
        },
        {
          id: 'sample-5',
          itemName: 'Amoxicillin 500mg Capsule',
          claimedPrice: 45,
          status: 'Admissible',
          approvedPrice: 45,
          reimbursementAmount: 35,
          category: 'Medicine'
        }
      ];

      setAnalysisResults(sampleResults);
      setShowDashboard(true);

      toast({
        title: "Sample Data Loaded",
        description: "Test analysis with sample medical data has been loaded successfully.",
      });
    } catch (error) {
      console.error('Sample data test failed:', error);
      toast({
        title: "Test Failed",
        description: "Failed to load sample data.",
        variant: "destructive"
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStartNew = () => {
    setAnalysisResults([]);
    setClaimItems([]);
    setPatientInfo({
      name: 'Patient Name Not Found',
      relation: 'Self'
    });
    setShowDashboard(false);
    setShowStructuredView(false);
    setTotalPages(0);
    setProcessingStatus('completed');
  };

  // Show structured claim results view
  if (showStructuredView && claimItems.length > 0) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b bg-card shadow-soft">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-gradient-medical p-2 rounded-lg">
                  <Stethoscope className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">Medical Claim Processor</h1>
                  <p className="text-muted-foreground">Smart extraction and reimbursement calculator</p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={() => { setShowStructuredView(false); setShowDashboard(true); }}
                  variant="outline"
                >
                  Switch to Analysis View
                </Button>
                <Button
                  onClick={handleStartNew}
                  className="bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  Start New Analysis
                </Button>
              </div>
            </div>
          </div>
        </header>
        
        <main className="container mx-auto px-4 py-8">
          <ClaimResults
            claimItems={claimItems}
            totalPages={totalPages}
            processingStatus={processingStatus}
            onUpdateClaim={handleUpdateClaim}
          />
        </main>
      </div>
    );
  }

  // Show traditional dashboard view
  if (showDashboard && analysisResults.length > 0) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b bg-card shadow-soft">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-gradient-medical p-2 rounded-lg">
                  <Stethoscope className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">Medical Bill Analyzer</h1>
                  <p className="text-muted-foreground">Professional healthcare document analysis</p>
                </div>
              </div>
              <button
                onClick={handleStartNew}
                className="bg-primary text-primary-foreground px-4 py-2 rounded-md hover:bg-primary/90 transition-colors"
              >
                Start New Analysis
              </button>
            </div>
          </div>
        </header>
        
        <main className="container mx-auto px-4 py-8">
          <Dashboard 
            analysisResults={analysisResults}
            patientInfo={patientInfo}
            onUpdateApprovedPrice={handleUpdateApprovedPrice}
            onUpdateReimbursementAmount={handleUpdateReimbursementAmount}
          />
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Hero Section */}
      <section className="bg-gradient-hero text-white py-20">
        <div className="container mx-auto px-4 text-center">
          <div className="flex justify-center mb-6">
            <div className="bg-white/10 p-4 rounded-2xl backdrop-blur-sm">
              <Stethoscope className="h-12 w-12" />
            </div>
          </div>
          <h1 className="text-4xl md:text-6xl font-bold mb-6">
            Medical Bill Analyzer
          </h1>
          <p className="text-xl md:text-2xl mb-8 opacity-90 max-w-3xl mx-auto">
            Intelligent document analysis for healthcare billing.
          </p>
          <div className="grid md:grid-cols-3 gap-6 max-w-4xl mx-auto text-left">
            <div className="bg-white/10 p-6 rounded-lg backdrop-blur-sm">
              <FileSearch className="h-8 w-8 mb-3" />
              <h3 className="font-semibold mb-2">Smart OCR Analysis</h3>
              <p className="text-sm opacity-80">Advanced text extraction from PDFs and images</p>
            </div>
            <div className="bg-white/10 p-6 rounded-lg backdrop-blur-sm">
              <Shield className="h-8 w-8 mb-3" />
              <h3 className="font-semibold mb-2">Compliance Checking</h3>
              <p className="text-sm opacity-80">Automatic validation against prescriptions</p>
            </div>
            <div className="bg-white/10 p-6 rounded-lg backdrop-blur-sm">
              <TrendingUp className="h-8 w-8 mb-3" />
              <h3 className="font-semibold mb-2">Detailed Reports</h3>
              <p className="text-sm opacity-80">Comprehensive analysis and downloadable reports</p>
            </div>
          </div>
        </div>
      </section>

      {/* Upload Section */}
      <section className="py-16">
        <div className="container mx-auto px-4 max-w-6xl">
          <Card className="shadow-medical">
            <CardHeader className="text-center">
              <CardTitle className="text-3xl font-bold mb-2">
                Start Your Analysis
              </CardTitle>
              <p className="text-muted-foreground">
                Upload your medical bills and prescriptions to begin the automated analysis process
              </p>
            </CardHeader>
            <CardContent className="p-8">
              <FileUploader 
                onFilesUploaded={handleFilesUploaded}
                isProcessing={isProcessing}
              />

              {/* Debug/Test Section */}
              <div className="mt-6 pt-6 border-t">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-muted-foreground">Testing Options</h3>
                    <p className="text-xs text-muted-foreground">Try the system with sample data</p>
                  </div>
                  <Button
                    onClick={handleTestWithSampleData}
                    variant="outline"
                    size="sm"
                    disabled={isProcessing}
                    className="text-xs"
                  >
                    Load Sample Data
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-card border-t py-6">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Stethoscope className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold">Medical Reimbursement Analysis System</span>
          </div>
          <p>Created by Gen AI Team</p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
