export type AttendanceRecord = {
  id?: string;
  Employee?: string | null;
  EmployeeLookupId?: string | number;
  EmployeeEmail?: string;
  EmployeeName?: string;
  AttendanceDate: string;
  LoginTime?: string;
  LogoutTime?: string;
  LastActivity?: string;
  Remarks?: string | null;
  WorkingHours: number;
  MeetingHours: number;
  AttendanceStatus: string;
  // Device/Asset fields (enriched from Employee record)
  AssetId?: string;
  AssetType?: string;
};

export type EmployeeProfile = {
  id?: string;
  Email: string;
  Title?: string;
  Department?: string;
  Manager?: string;
  MicrosoftUserId?: string;
  AssetId?: string;
  AssetType?: string;
  PersonalNumber?: string;
  CompanyNumber?: string;
};
  [key: string]: unknown;
};
