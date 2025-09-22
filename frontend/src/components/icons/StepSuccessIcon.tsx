import React from 'react';

const StepSuccessIcon: React.FC = () => {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      width="16" 
      height="16" 
      viewBox="0 0 24 24" 
      fill="none"
      stroke="var(--function-success)" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
      className="lucide lucide-check relative top-[2px] flex-shrink-0"
    >
      <path d="M20 6 9 17l-5-5"></path>
    </svg>
  );
};

export default StepSuccessIcon; 