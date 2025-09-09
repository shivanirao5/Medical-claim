import React, { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Edit2, Save, X, FileText, Pill, TestTube, Stethoscope } from "lucide-react";

// ClaimResults is a presentational component that displays structured
// claim items returned by the backend. It provides lightweight local
// editing for reimbursement and other numeric fields so users can correct
// OCR mistakes before exporting or approving claims.

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

interface ClaimResultsProps {
  claimItems: ClaimItem[];
  totalPages: number;
  processingStatus: string;
  onUpdateClaim: (index: number, updatedClaim: ClaimItem) => void;
}

export const ClaimResults: React.FC<ClaimResultsProps> = ({
  claimItems,
  totalPages,
  processingStatus,
  onUpdateClaim
}) => {
  // Local UI state for which row is being edited and the draft values
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editData, setEditData] = useState<ClaimItem | null>(null);

  // Begin editing a row: clone the claim item into local state
  const handleEdit = (index: number) => {
    setEditingIndex(index);
    setEditData({ ...claimItems[index] });
  };

  // Save changes by calling the parent update handler; parent may persist
  // the change or simply update local state. We intentionally keep this
  // component dumb about persistence concerns.
  const handleSave = (index: number) => {
    if (editData) {
      onUpdateClaim(index, editData);
      setEditingIndex(null);
      setEditData(null);
    }
  };

  const handleCancel = () => {
    setEditingIndex(null);
    setEditData(null);
  };

  const handleInputChange = (field: keyof ClaimItem, value: any) => {
    if (editData) {
      setEditData({ ...editData, [field]: value });
    }
  };

  // Format numbers as Indian Rupee currency for display
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR'
    }).format(amount);
  };

  const getTotalAmount = (item: ClaimItem) => {
    return item.amount_spent_on_medicine + item.amount_spent_on_test + item.amount_spent_on_consultation;
  };

  // Empty state: guide user to upload documents
  if (!claimItems || claimItems.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">
          <p className="text-center text-muted-foreground">No claim items found. Please upload a medical bill or prescription.</p>
        </CardContent>
      </Card>
    );
  }

  // Main UI: summary cards followed by an editable table of claim items
  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <FileText className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-sm font-medium">Total Pages</p>
                <p className="text-2xl font-bold">{totalPages}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Pill className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-sm font-medium">Total Medicine Cost</p>
                <p className="text-2xl font-bold">
                  {formatCurrency(claimItems.reduce((sum, item) => sum + item.amount_spent_on_medicine, 0))}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <TestTube className="h-4 w-4 text-purple-500" />
              <div>
                <p className="text-sm font-medium">Total Test Cost</p>
                <p className="text-2xl font-bold">
                  {formatCurrency(claimItems.reduce((sum, item) => sum + item.amount_spent_on_test, 0))}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center space-x-2">
              <Stethoscope className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-sm font-medium">Total Reimbursement</p>
                <p className="text-2xl font-bold text-green-600">
                  {formatCurrency(claimItems.reduce((sum, item) => sum + item.reimbursement_amount, 0))}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Claims Table */}
      <Card>
        <CardHeader>
          <CardTitle>Medical Claims ({claimItems.length} items)</CardTitle>
          <CardDescription>
            Processing Status: <Badge variant={processingStatus === 'completed' ? 'default' : 'secondary'}>
              {processingStatus}
            </Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Bill No.</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Medicine Cost</TableHead>
                  <TableHead>Test Cost</TableHead>
                  <TableHead>Consultation Cost</TableHead>
                  <TableHead>Doctor</TableHead>
                  <TableHead>Hospital</TableHead>
                  <TableHead>Medicines</TableHead>
                  <TableHead>Tests</TableHead>
                  <TableHead>Reimbursement</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {claimItems.map((item, index) => (
                  <TableRow key={index}>
                    <TableCell className="font-medium">
                      {editingIndex === index ? (
                        <Input
                          value={editData?.bill_no || ''}
                          onChange={(e) => handleInputChange('bill_no', e.target.value)}
                          className="w-32"
                        />
                      ) : (
                        item.bill_no
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          value={editData?.my_date || ''}
                          onChange={(e) => handleInputChange('my_date', e.target.value)}
                          className="w-32"
                        />
                      ) : (
                        item.my_date
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          type="number"
                          value={editData?.amount_spent_on_medicine || 0}
                          onChange={(e) => handleInputChange('amount_spent_on_medicine', parseFloat(e.target.value) || 0)}
                          className="w-24"
                        />
                      ) : (
                        formatCurrency(item.amount_spent_on_medicine)
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          type="number"
                          value={editData?.amount_spent_on_test || 0}
                          onChange={(e) => handleInputChange('amount_spent_on_test', parseFloat(e.target.value) || 0)}
                          className="w-24"
                        />
                      ) : (
                        formatCurrency(item.amount_spent_on_test)
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          type="number"
                          value={editData?.amount_spent_on_consultation || 0}
                          onChange={(e) => handleInputChange('amount_spent_on_consultation', parseFloat(e.target.value) || 0)}
                          className="w-24"
                        />
                      ) : (
                        formatCurrency(item.amount_spent_on_consultation)
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          value={editData?.doctor_name || ''}
                          onChange={(e) => handleInputChange('doctor_name', e.target.value)}
                          className="w-32"
                        />
                      ) : (
                        item.doctor_name || 'N/A'
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <Input
                          value={editData?.hospital_name || ''}
                          onChange={(e) => handleInputChange('hospital_name', e.target.value)}
                          className="w-32"
                        />
                      ) : (
                        item.hospital_name || 'N/A'
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {item.medicine_names.map((med, idx) => (
                          <Badge key={idx} variant="secondary" className="text-xs">
                            {med}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {item.test_names.map((test, idx) => (
                          <Badge key={idx} variant="outline" className="text-xs">
                            {test}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="font-bold text-green-600">
                      {editingIndex === index ? (
                        <Input
                          type="number"
                          value={editData?.reimbursement_amount || 0}
                          onChange={(e) => handleInputChange('reimbursement_amount', parseFloat(e.target.value) || 0)}
                          className="w-24"
                        />
                      ) : (
                        formatCurrency(item.reimbursement_amount)
                      )}
                    </TableCell>
                    <TableCell>
                      {editingIndex === index ? (
                        <div className="flex space-x-2">
                          <Button
                            size="sm"
                            onClick={() => handleSave(index)}
                            className="h-8 w-8 p-0"
                          >
                            <Save className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={handleCancel}
                            className="h-8 w-8 p-0"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleEdit(index)}
                          className="h-8 w-8 p-0"
                          disabled={!item.editable}
                        >
                          <Edit2 className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ClaimResults;
