import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Download, Save, CheckCircle, XCircle, IndianRupee } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { generateReport } from '@/lib/reportGenerator';

export interface AnalysisItem {
  id: string;
  itemName: string;
  claimedPrice: number;
  status: 'Admissible' | 'Not Admissible';
  approvedPrice: number;
  reimbursementAmount?: number;
  category?: string;
}

export interface PatientInfo {
  name: string;
  relation: 'Self' | 'Spouse' | 'Child' | 'Parent' | 'Sibling' | 'Other';
  age?: number;
  gender?: 'Male' | 'Female' | 'Other';
}

interface DashboardProps {
  analysisResults: AnalysisItem[];
  patientInfo: PatientInfo;
  onUpdateApprovedPrice: (id: string, price: number) => void;
  onUpdateReimbursementAmount: (id: string, amount: number) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ 
  analysisResults, 
  patientInfo,
  onUpdateApprovedPrice,
  onUpdateReimbursementAmount 
}) => {
  const [editingPrice, setEditingPrice] = useState<string | null>(null);
  const [tempPrice, setTempPrice] = useState<string>('');
  const [editingReimbursement, setEditingReimbursement] = useState<string | null>(null);
  const [tempReimbursement, setTempReimbursement] = useState<string>('');
  const { toast } = useToast();

  const claimedTotal = analysisResults.reduce((sum, item) => sum + item.claimedPrice, 0);
  const approvedTotal = analysisResults.reduce((sum, item) => sum + item.approvedPrice, 0);
  const reimbursementTotal = analysisResults.reduce((sum, item) => sum + (item.reimbursementAmount || 0), 0);
  const rejectedTotal = claimedTotal - approvedTotal;

  const admissibleItems = analysisResults.filter(item => item.status === 'Admissible');
  const notAdmissibleItems = analysisResults.filter(item => item.status === 'Not Admissible');

  const handleEditPrice = (id: string, currentPrice: number) => {
    setEditingPrice(id);
    setTempPrice(currentPrice.toString());
  };

  const handleSavePrice = (id: string) => {
    const price = parseFloat(tempPrice);
    if (!isNaN(price) && price >= 0) {
      onUpdateApprovedPrice(id, price);
      setEditingPrice(null);
      setTempPrice('');
    }
  };

  const handleCancelEdit = () => {
    setEditingPrice(null);
    setTempPrice('');
  };

  const handleEditReimbursement = (id: string, currentAmount: number) => {
    setEditingReimbursement(id);
    setTempReimbursement(currentAmount.toString());
  };

  const handleSaveReimbursement = (id: string) => {
    const amount = parseFloat(tempReimbursement);
    if (!isNaN(amount) && amount >= 0) {
      onUpdateReimbursementAmount(id, amount);
      setEditingReimbursement(null);
      setTempReimbursement('');
    }
  };

  const handleCancelReimbursementEdit = () => {
    setEditingReimbursement(null);
    setTempReimbursement('');
  };

  const handleSaveToStorage = () => {
    const dataToSave = {
      timestamp: new Date().toISOString(),
      analysisResults,
      totals: {
        claimed: claimedTotal,
        approved: approvedTotal,
        rejected: rejectedTotal
      }
    };

    localStorage.setItem('medicalBillAnalysis', JSON.stringify(dataToSave));
    toast({
      title: "Analysis Saved",
      description: "Your analysis has been saved successfully to local storage.",
    });
  };

  const handleDownloadReport = async () => {
    try {
      await generateReport(analysisResults, {
        claimed: claimedTotal,
        approved: approvedTotal,
        rejected: rejectedTotal,
        reimbursed: reimbursementTotal
      }, patientInfo);
      toast({
        title: "Report Downloaded",
        description: "Your analysis report has been downloaded as a DOCX file.",
      });
    } catch (error) {
      toast({
        title: "Download Failed",
        description: "Failed to generate report. Please try again.",
        variant: "destructive"
      });
    }
  };

  const SummaryCard = ({ title, amount, icon, variant = "default" }: {
    title: string;
    amount: number;
    icon: React.ReactNode;
    variant?: "default" | "success" | "destructive" | "warning";
  }) => {
    const variantClasses = {
      default: "bg-card",
      success: "bg-accent-light border-accent",
      destructive: "bg-destructive/10 border-destructive",
      warning: "bg-warning-light border-warning"
    };

    return (
      <Card className={`${variantClasses[variant]} shadow-soft`}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-muted-foreground">{title}</p>
              <div className="flex items-center gap-1 mt-1">
                <IndianRupee className="h-5 w-5" />
                <span className="text-2xl font-bold">{amount.toLocaleString('en-IN')}</span>
              </div>
            </div>
            <div className="text-muted-foreground">{icon}</div>
          </div>
        </CardContent>
      </Card>
    );
  };

  if (analysisResults.length === 0) {
    return (
      <Card className="text-center p-8">
        <CardContent>
          <p className="text-muted-foreground">No analysis results yet. Upload documents to get started.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Analysis Dashboard</h2>
          <p className="text-muted-foreground">Review and approve medical bill items</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleSaveToStorage} variant="outline">
            <Save className="mr-2 h-4 w-4" />
            Save Analysis
          </Button>
          <Button onClick={handleDownloadReport} className="bg-gradient-medical">
            <Download className="mr-2 h-4 w-4" />
            Download Report
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          title="Total Claimed"
          amount={claimedTotal}
          icon={<IndianRupee className="h-6 w-6" />}
          variant="warning"
        />
        <SummaryCard
          title="Total Approved"
          amount={approvedTotal}
          icon={<CheckCircle className="h-6 w-6" />}
          variant="success"
        />
        <SummaryCard
          title="Total Reimbursed"
          amount={reimbursementTotal}
          icon={<IndianRupee className="h-6 w-6" />}
          variant="default"
        />
        <SummaryCard
          title="Total Rejected"
          amount={rejectedTotal}
          icon={<XCircle className="h-6 w-6" />}
          variant="destructive"
        />
      </div>

      {/* Patient Information Card */}
      <Card className="shadow-soft border-primary">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <div className="bg-primary/10 p-2 rounded-lg">
              <CheckCircle className="h-5 w-5 text-primary" />
            </div>
            Patient Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Patient Name</p>
              <p className="text-lg font-semibold">{patientInfo.name}</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Relation</p>
              <Badge variant="secondary" className="text-sm">
                {patientInfo.relation}
              </Badge>
            </div>
            {patientInfo.age && (
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Age</p>
                <p className="text-lg font-semibold">{patientInfo.age} years</p>
              </div>
            )}
            {patientInfo.gender && (
              <div className="space-y-1">
                <p className="text-sm font-medium text-muted-foreground">Gender</p>
                <Badge variant="outline" className="text-sm">
                  {patientInfo.gender}
                </Badge>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Analysis Results Table */}
      <Card className="shadow-medical">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            Analysis Results
            <Badge variant="secondary">
              {analysisResults.length} items analyzed
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Claimed Price</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Approved Price</TableHead>
                  <TableHead>Reimbursement</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {analysisResults.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.itemName}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.category || 'General'}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <IndianRupee className="h-3 w-3" />
                        {item.claimedPrice.toLocaleString('en-IN')}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant={item.status === 'Admissible' ? 'default' : 'destructive'}
                        className={item.status === 'Admissible' ? 'bg-accent' : ''}
                      >
                        {item.status === 'Admissible' ? (
                          <CheckCircle className="mr-1 h-3 w-3" />
                        ) : (
                          <XCircle className="mr-1 h-3 w-3" />
                        )}
                        {item.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {editingPrice === item.id ? (
                        <div className="flex items-center gap-2">
                          <div className="flex items-center">
                            <IndianRupee className="h-3 w-3 text-muted-foreground" />
                            <Input
                              type="number"
                              value={tempPrice}
                              onChange={(e) => setTempPrice(e.target.value)}
                              className="w-24 h-8"
                              min="0"
                              step="0.01"
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <IndianRupee className="h-3 w-3" />
                          {item.approvedPrice.toLocaleString('en-IN')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      {editingReimbursement === item.id ? (
                        <div className="flex items-center gap-2">
                          <div className="flex items-center">
                            <IndianRupee className="h-3 w-3 text-muted-foreground" />
                            <Input
                              type="number"
                              value={tempReimbursement}
                              onChange={(e) => setTempReimbursement(e.target.value)}
                              className="w-24 h-8"
                              min="0"
                              step="0.01"
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <IndianRupee className="h-3 w-3" />
                          {(item.reimbursementAmount || 0).toLocaleString('en-IN')}
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {editingPrice === item.id ? (
                          <>
                            <Button
                              size="sm"
                              onClick={() => handleSavePrice(item.id)}
                              className="h-7"
                            >
                              Save Price
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={handleCancelEdit}
                              className="h-7"
                            >
                              Cancel
                            </Button>
                          </>
                        ) : editingReimbursement === item.id ? (
                          <>
                            <Button
                              size="sm"
                              onClick={() => handleSaveReimbursement(item.id)}
                              className="h-7"
                            >
                              Save Reimb
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={handleCancelReimbursementEdit}
                              className="h-7"
                            >
                              Cancel
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleEditPrice(item.id, item.approvedPrice)}
                              className="h-7"
                            >
                              Edit Price
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleEditReimbursement(item.id, item.reimbursementAmount || 0)}
                              className="h-7"
                            >
                              Edit Reimb
                            </Button>
                          </>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Analysis Summary */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="shadow-soft border-accent">
          <CardHeader>
            <CardTitle className="text-accent flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              Admissible Items ({admissibleItems.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {admissibleItems.slice(0, 5).map((item) => (
                <div key={item.id} className="flex justify-between items-center text-sm">
                  <span className="truncate">{item.itemName}</span>
                  <div className="flex items-center gap-1">
                    <IndianRupee className="h-3 w-3" />
                    <span>{item.approvedPrice.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              ))}
              {admissibleItems.length > 5 && (
                <p className="text-xs text-muted-foreground">
                  +{admissibleItems.length - 5} more items...
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-soft border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <XCircle className="h-5 w-5" />
              Not Admissible Items ({notAdmissibleItems.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {notAdmissibleItems.slice(0, 5).map((item) => (
                <div key={item.id} className="flex justify-between items-center text-sm">
                  <span className="truncate">{item.itemName}</span>
                  <div className="flex items-center gap-1">
                    <IndianRupee className="h-3 w-3" />
                    <span>{item.claimedPrice.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              ))}
              {notAdmissibleItems.length > 5 && (
                <p className="text-xs text-muted-foreground">
                  +{notAdmissibleItems.length - 5} more items...
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};